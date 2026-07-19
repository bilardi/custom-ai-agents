---
title: "Da un SYSTEM prompt ad un multi-agente in locale su IDE"
date: 2026-07-20
categories: [agentic]
tags: [ollama, rag, slm, fastapi]
repo: bilardi/custom-ai-agents
---

![Architecture](images/flowchart.png)

## Ollama non mi bastava più

Negli ultimi anni sono nate come funghi estensioni per gli IDE che parlano direttamente con Language Model (LM), piccoli o grandi (SLM, LLM), o con piattaforme agentiche. E dall'inizio, la prima domanda era: cosa c'è di open source ? Ho provato [Ollama](https://ollama.com/) in locale: funziona, è privato, non costa nulla.

Ma il solo SYSTEM prompt non mi bastava più: volevo usare dei `/tag`, e appoggiarmi a una RAG (Retrieval-Augmented Generation) locale sulla documentazione che mi serve. E, già che c'ero, preparare una base per sperimentare l'agentica.

La seconda domanda che mi ha portato a scrivere l'articolo è stata: chi decide cosa fare con quel messaggio ? Rispondere con la conoscenza del modello, interrogare la RAG, cercare sul web, o generare codice sono quattro strade, e sceglierle è un grado di libertà che si paga. Più lascio decidere al LM, più il sistema diventa flessibile ma meno prevedibile, testabile e a costo noto.

Prima di tutto c'è il livello zero: un custom model che non decide nulla ma risponde con il SYSTEM prompt fornito. Da lì si sale, quattro gradini in tutto:

| Engine | Chi decide il routing | Testabile senza LM | Flessibilità | Costo/complessità |
|---|---|---|---|---|
| 0. SYSTEM (custom model) | nessuno: genera e basta | no | minima | nullo |
| A. router deterministico | regole fisse (`/tag`, URL, `/web`) | sì, funzione pura | bassa | basso |
| B. agente + tool | il LM | no (mock del LM) | alta | medio |
| C. orchestratore + agent-as-tool | il LM, con uno specialista sotto | no | alta | medio-alto |
| D. multi-agente con handoff | gli agenti, fra pari | no | molto alta | alto |

Da buon informatico pigro, aggiungo quanto basta: sono passata ad A, la versione dello scettico, quella che gira secondo regole fisse (i `/tag`) e si testa come codice puro, e ho aggiunto complessità quando dimostravo che non bastava più.

Un dettaglio che aiuta a leggere la scala: basta un solo agent-as-tool per essere già multi-agente. Il discriminante non è quanti agenti ci sono, ma chi tiene il controllo della conversazione:
- un solo agente parla con l'utente e interpella gli altri come tool (agent-as-tool): li usa come consulenti, ne riceve un risultato e il controllo resta sempre suo
- più agenti si passano il controllo (handoff): chi riceve la conversazione la prende in mano, dialoga con l'utente e può cederla ad un altro; gli agenti sono cooperanti

## Un engine per ogni grado di libertà

I quattro engine coesistono nello stesso codice e si possono confrontare fianco a fianco cambiando una variabile: la struttura completa sta nel [README](https://github.com/bilardi/custom-ai-agents), qui racconto gli esperimenti.

![Engine deterministico](images/engine-deterministic.png)

A, il deterministico, fornisce al LM solo il materiale che l'utente decide: con uno specifico `/tag` si interroga il topic di una RAG, se c'è un URL viene recuperato il suo contenuto, `/web` cerca sul web, e tutto il resto passa dritto al modello. Nessuna decisione è del LM, che fa solo la sintesi finale del testo dal contesto fornito. Con la dependency injection ovunque (le dipendenze, come il client della RAG o le sessioni HTTP, non le crea l'engine: le riceve dall'esterno, ed è questo che nei test mi lascia sostituirle con dei mock senza toccare il codice), questo engine si copre interamente con test veloci e offline: c'è un metodo che interroga la RAG, un metodo che recupera il contenuto di un URL e un metodo che recupera i risultati di una ricerca web; il LM entra solo nella generazione, e nei test viene mockato. Proprio il comportamento di default, il pass-through (la domanda inoltrata al modello così com'è, senza contesto aggiunto), rivela il limite: decidere "so rispondere da solo o mi conviene cercare sul web ?" non è esprimibile con una regola, è una decisione del LM. Questa è la ragione per salire a B.

![Engine tool-agent](images/engine-tool-agent.png)

B, il tool-agent, mette il LM al posto delle regole: un orchestratore decide quali metodi usare, se la RAG, l'URL o il web. Questi metodi diventano i suoi tool, e li sceglie emettendo una tool-call (la chiamata strutturata con cui il modello invoca un metodo) in base alla loro descrizione: la docstring dei metodi è il contratto che l'agente legge per sceglierli. I tool restano le stesse funzioni pure di A, testabili senza LM: qui a non esserlo è solo la scelta di quale chiamare, che spetta al modello. Ma il rischio non è solo chiamare il tool sbagliato, è usarne o meno l'output: chiamare un tool non significa poggiare la risposta su ciò che restituisce. È il grounding (la risposta che si fonda sui contenuti recuperati invece di inventarli), e non lo garantisce il meccanismo agentico; per ottenerlo c'è il prompt (l'istruzione che vincola il modello ad ancorarsi al contenuto recuperato o a dire che la documentazione non copre la domanda), e poi il retrieval: provare più embedder (i modelli che trasformano il testo in vettori per la ricerca per similarità) e regolare parametri come la dimensione dei chunk (i pezzi in cui spezzo i documenti), fino alla combinazione giusta (dettaglio nel benchmark [grounding](https://github.com/bilardi/custom-ai-agents/blob/master/benchmark/grounding.md)). Un agente con tool basta quando il dominio è uno solo: per specializzarne una parte si sale a C.

![Engine agent-as-tool](images/engine-agent-as-tool.png)

C, l'agent-as-tool, aggiunge una specializzazione senza riscrivere l'architettura: un coder che l'orchestratore consulta come fosse un tool e da cui riceve il codice, mentre il controllo resta suo. Il coder è un LM che non riparte da zero: riceve il contesto già recuperato dall'orchestratore e, se gli serve altro, può chiamare a sua volta i tool (per esempio `retrieve`, per arricchirsi con altra documentazione dalla RAG). Consultare un sotto-agente, però, annida le chiamate: l'orchestratore chiama il coder, che a sua volta lavora e interroga i suoi tool, quindi più latenza. Un multi-agente pieno qui sarebbe over-engineering: il coder è un consulto, non un trasferimento di controllo.

![Engine multi-agente](images/engine-multi-agent.png)

D, il multi-agente, è l'ultimo gradino: non più un consulto ma un handoff, il controllo che passa da un agente all'altro. Un triage sceglie lo specialista giusto e gli passa il testimone; sotto al cofano è una tool-call come quella di B, verso un altro LM. Se il modello non la emette in modo affidabile il passaggio non avviene e la conversazione resta al triage. L'handoff serve solo quando cedere il controllo è davvero necessario; per un semplice consulto basta C.

Ogni gradino è un baratto, in una riga:
- A non decide ma è gratis e testabile
- B decide ma non è più prevedibile
- C specializza ma annida più chiamate
- D trasferisce il controllo ma vuole tool-call affidabili

Da buon sviluppatore, ogni baratto l'ho verificato con un benchmark riproducibile: uno per A, B, C e D.

## Rompicapo e performance

### Quello che il mock non vedeva

Quando iniziai a fare le prime sperimentazioni, non c'erano estensioni IDE che permettessero di usare URL personali, quindi tutto è partito simulando le API di Ollama con [FastAPI](https://fastapi.tiangolo.com/): un'altra tecnologia che raccomando, un'API REST con validazione integrata che si monta in poche righe.

Le unit test coprivano i tool e parte della simulazione di Ollama, ma il grosso era da testare usandolo e vedendo cosa mancava ancora: documentazione di Ollama ce n'è, però non avevo intenzione di implementare tutte le API, solo quelle strettamente necessarie.

E poi c'era il formato di risposta che non era quello che il client Ollama si aspettava: un JSON singolo quando non c'è streaming, NDJSON (un oggetto JSON per riga) quando c'è. Piccole cose, ognuna capace di far sembrare rotto tutto il resto.

Il punto importante è stato testare tutto quello che era invisibile nel codice, ma gestito dalla libreria [any_agent](https://github.com/mozilla-ai/any-agent), che supporta diversi framework agentici.

Con async e await ho sempre avuto scontri accesi, e da informatico pigro avevo scelto la via più comoda: un framework sincrono, [smolagents](https://github.com/huggingface/smolagents).

Solo che alla seconda chiamata al LM arrivava un `RuntimeError: Event loop is closed`. La causa non era nel mio codice, era proprio l'uso di un framework sincrono in un contesto asincrono, con un bridge che crea e chiude un event loop a ogni chiamata mentre il client di Ollama, invece, persiste. La soluzione è stata passare al framework [tinyagent](https://github.com/mozilla-ai/any-agent), con il runtime asincrono nativo di any_agent: un solo loop per tutta la richiesta, e il client resta valido tra i passi.

### I modelli piccoli e la tool-call

Si parla sempre di modelli gestibili con Ollama e usabili su una GPU da portatile: llama3.2:3b e qwen2.5 sono stati quelli più performanti, ma hanno avuto i loro alti e bassi.

Con l'uso dell'engine agent-as-tool, la delega dell'orchestratore si è rivelata la parte fragile. La delega è la decisione dell'orchestratore di chiamare il coder invece di rispondere da sé: con i chunk del retrieve già in mano rispondeva da solo, allucinando pure un'API inesistente. Con un prompt generico non delegava: è servito un prompt dedicato che lo obbligasse a delegare i compiti di codice (dettaglio nel [orchestrator](https://github.com/bilardi/custom-ai-agents/blob/master/benchmark/orchestrator.md#orchestrator-prompt-agent_as_tool)).

Delega e tool-call sono legate ma distinte. La delega è una scelta del modello, orientabile con il prompt. La tool-call è il meccanismo con cui il modello invoca un tool, il coder compreso: è su questo meccanismo che agiscono gli accorgimenti che seguono, dove la tool-call è la protagonista.

- **tinyagent non gestisce la tool-call con `/api/chat`**: col provider nativo di Ollama la tool-call torna come testo e non viene riconosciuta; con l'endpoint OpenAI-compatibile `/v1` arriva nel formato strutturato del function-calling (lo standard con cui il modello dichiara quale tool chiamare e con quali argomenti) e tinyagent la legge. In questo modo, llama3.2:3b passa da non-parsabile a delegare nell'80% dei casi (dettaglio nel [orchestrator](https://github.com/bilardi/custom-ai-agents/blob/master/benchmark/orchestrator.md#results-via-v1))
- **qwen2.5 aggiunge argomenti di troppo**: inietta a volte nella chiamata anche `toolbench_rapidapi_key` (un parametro di autenticazione che i tool implementati non avevano), e la chiamata fallisce; la patch è stata assorbire gli argomenti extra con un `**kwargs` nella firma di tutti i tool
- **con llama3.2:3b, la tool-call finisce nel testo**: a volte scrive la tool-call come testo nella risposta finale (`{"name": ...}`, `<|python_tag|>`) e all'utente arriva una risposta poco utile o incomprensibile; con un guard deterministico nell'engine, queste situazioni sono riconosciute e viene rilanciato l'orchestratore: i malformati scendono dal ~20% al ~10%, e la delega sale al 90% (dettaglio nel [orchestrator](https://github.com/bilardi/custom-ai-agents/blob/master/benchmark/orchestrator.md#anti-malformed-guard-the-turning-point))
- **l'handoff multi-agente è una tool-call**: il triage passa il controllo a uno specialista proprio emettendola, ma via l'[OpenAI Agents SDK](https://github.com/openai/openai-agents-python), che è l'unico framework che any_agent cabla per l'handoff: tinyagent e gli altri non lo fanno; e così llama3.2:3b riesce a passare nel 60% dei casi contro il 90% di un modello più capace come qwen2.5 (dettaglio nel [multi_agent](https://github.com/bilardi/custom-ai-agents/blob/master/benchmark/multi_agent.md#results-n5))

Prima di restituire il codice, il coder lo passa a un controllo deterministico sulla sintassi (con `ruff` come segnale): non il guard di prima, che vigila sulla risposta dell'orchestratore, ma un code_validator sul codice generato. Non prende tutto, però: un'API inventata è sintatticamente valida e passa il vaglio. Per prendere questi casi ho aggiunto il reviewer, un secondo agente LM che rilegge il codice del coder e ne giudica la semantica: risponde al task ? usa API che esistono davvero ? È l'unico accorgimento che con la tool-call non c'entra, e l'unico che non ha ripagato sul modello piccolo: su llama3.2:3b boccia tutto, 100% di falsi positivi, segnalando come sbagliato anche il codice giusto, quindi come filtro non serve. Su qwen2.5, più capace, comincia a discriminare: coglie il 90% delle API inventate, ma segnala ancora a torto il 45% del codice corretto (dettaglio nel [reviewer](https://github.com/bilardi/custom-ai-agents/blob/master/benchmark/reviewer.md#results)). Per questo l'ho reso opzionale, utile solo con un modello più grande.

### I due piani

Ero partita dalla versione dello scettico: un sistema deterministico, prevedibile e testabile. Il sistema deterministico è la parte più utile in locale: modello veloce, niente tool-calling fragile, retrieval buono, è quella che si può usare davvero. L'agentica, su hardware modesto, sembrava solo una sperimentazione; ma con i tre interventi mirati (l'endpoint `/v1`, il prompt di delega, il guard) arriva a dare qualcosa di sensato al 90% delle volte, pur con risorse limitate: i malformati ci possono essere, e questo ci ricorda che si sta lavorando con un sistema non deterministico.

## Cosa si può esplorare ancora ?

Alcuni degli approfondimenti che seguono non sono solo miglioramenti, ma vere e proprie storie da sviscerare, sempre nell'interesse di esplorare le tecnologie a disposizione da sfruttare in locale.

La scelta del backend di augmented generation potrebbe cambiare in base alla necessità. Qui è stato usato [ChromaDB](https://www.trychroma.com/), ma l'interfaccia `Retriever` è già disegnata per accogliere un backend vettoriale diverso o un grafo; potrebbero comunque esserci valide alternative, come gli [MCP](https://modelcontextprotocol.io/) (Model Context Protocol) a gestione locale che stanno nascendo. E, indipendentemente da questo, resta da esplorare l'elaborazione della documentazione in modo deterministico. Quando e quale conviene, e dove mettere le parti di indicizzazione condivise, è un tema a sé.

Sempre sulla gestione della documentazione, un'altra strada è migliorare il prompt o i tool a disposizione del coder e del reviewer:
- avere un sistema che fornisca tutte le firme con descrizioni al coder, migliorerebbe moltissimo la sua risposta
- avere un sistema deterministico che individua dalla risposta del coder le firme usate, e uno che fornisce le firme più simili direttamente dalla documentazione, darebbe al reviewer un metro di giudizio migliore

E per chiudere, la scelta del framework multi-agente per la forma del coordinamento: qui l'handoff passa dall'unico framework che any_agent cabla per questo (OpenAI Agents SDK). Un confronto vero fra le alternative dipende dal tipo di multi-agente che serve, non da un caso minimo come questo, con due soli specialisti (Python e AWS).

L'idea di fondo è quella di spaziare per conoscere tutte queste tecnologie, toccarne i limiti, e capire cosa regge in locale e cosa no. Qualcosa sta in piedi su una GPU da portatile; altro richiede un modello più capace, a meno che nuove tecnologie non possano favorirne uno meno performante, per esempio, migliorandone il contesto. Sapere dove ogni tecnologia si ferma è già mezzo lavoro per il progetto di domani.
