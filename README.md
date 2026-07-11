# Custom AI Agents

An app that mimics the Ollama API so it can be used from any Ollama-compatible IDE extension, adding `/tag` routing and a local RAG over ChromaDB.

## Prerequisites

- [Ollama](https://ollama.com/download) with a pulled model (e.g. `qwen3`)
- Python 3.13
- [uv](https://docs.astral.sh/uv/)

## Usage

The proxy runs in front of Ollama, so any Ollama-compatible IDE extension can talk to the proxy on the default port: keep Ollama on `11435` and the proxy on `11434`.

### Ollama setup

Move Ollama off the default port so the proxy can take `11434`. Edit the service:

```sh
sudo systemctl edit ollama.service
```

```
[Service]
Environment="OLLAMA_DEBUG=1"
Environment="OLLAMA_ORIGINS=*"
Environment="OLLAMA_CONTEXT_LENGTH=40000"
Environment="OLLAMA_HOST=0.0.0.0:11435"
```

```sh
sudo systemctl restart ollama.service
```

With a non-default host, the CLI must target it explicitly:

```sh
OLLAMA_HOST=127.0.0.1:11435 ollama ps
```

Pull the default model and the embedder; optionally create the `coding` custom model - built from `modelfiles/Modelfile` (base `qwen2.5` + a `SYSTEM` prompt for a coding-assistant style), used only by `ENGINE=deterministic` with `MODEL=coding` (see Engines):

```sh
ollama pull llama3.2:3b
ollama pull nomic-embed-text
# optional: the coding custom model, used only by ENGINE=deterministic with MODEL=coding
ollama pull qwen2.5
ollama create coding -f modelfiles/Modelfile
```

### End-to-end test

| Variable | Default | Controls |
|---|---|---|
| `ENGINE` | `deterministic` | which engine handles messages: `deterministic`, `tool-agent`, `agent-as-tool` (`multi-agent` later) |
| `SHOW_TOOL_TRACE` | unset | `tool-agent`/`agent-as-tool`: stream a progress line per tool call to the IDE (e.g. `> reading local docs on 'dask'...`) |
| `MODEL` | `llama3.2:3b` | Ollama model for generation / the orchestrator (reached via `/v1`); best small local model that delegates reliably |
| `CODER_MODEL` | `MODEL` | `agent-as-tool` only: coder sub-agent model. On limited VRAM keep it equal to `MODEL` (one model loaded); `coding` gives no benefit here (the coder's prompt overrides its `SYSTEM`), use `qwen2.5` for better code only with spare VRAM |
| `REVIEW` | unset | `agent-as-tool` only: opt-in LLM reviewer of the coder's output. Off by default: on a small local model it flags everything (no discriminating signal, see [benchmark/reviewer.md](benchmark/reviewer.md)); the coder's deterministic check (syntax/ruff) stays. Enable with a capable `REVIEWER_MODEL` |
| `REVIEWER_MODEL` | `CODER_MODEL` | `agent-as-tool` only, when `REVIEW` is on: model for the reviewer sub-agent (use a capable model, e.g. `qwen2.5`) |
| `EMBED_MODEL` | `nomic-embed-text` | Ollama model used for embeddings; a dedicated retrieval model beats a general LLM and must match the index |
| `OLLAMA_URL` | `http://localhost:11434` | base URL of the Ollama server |
| `TOP_K` | `3` | number of RAG chunks retrieved per query; raise it to reach thinly documented topics |
| `MAX_WORDS` | `500` | chunk size in words (indexing); larger chunks keep an articulated topic whole and rank better |
| `OVERLAP` | `0` | chunk overlap in words (indexing); helps only when chunks are small enough to split a topic |
| `CONTEXT_LENGTH` | unset | generation context window (Ollama `num_ctx`); lower = faster |
| `HISTORY` | `1` | trailing conversation messages passed to the engine (`1` = last message only, `0` = all). Raise it (e.g. `50`) for multi-turn with a larger `MODEL`; small models degrade tool-calling on long context. The `deterministic` engine ignores it (routes on the last message) |
| `COLLECTION` | `dask` | topic to index (storage script) |
| `DOCS_FOLDER` | `data/documents/dask` | folder to index (storage script) |
| `RESET` | `false` | storage script: `true` wipes the collection before indexing (re-index from scratch), otherwise it appends |

Copy the template and edit your values:

```sh
cp .env.example .env
```

To use the coding-assistant persona (the `coding` model created above), set `MODEL=coding` in `.env`. It applies only to `ENGINE=deterministic` (and to an IDE talking to `coding` directly): the agent engines send their own system prompt (`prompts/coder.md`, `prompts/agent_as_tool.md`), which overrides the Modelfile `SYSTEM`, so the persona has no effect there.

End-to-end test (Ollama must be running):

1. index a topic (set `RESET=true` in `.env` to rebuild from scratch, e.g. after changing `EMBED_MODEL`, `MAX_WORDS` or `OVERLAP`; the embedding model must match between indexing and querying):
   ```sh
   uv run --env-file .env python -m scripts.document_manager.storage
   ```
2. list the indexed topics:
   ```sh
   uv run --env-file .env python -m scripts.document_manager.check_chunks
   ```
3. run the proxy:
   ```sh
   uv run --env-file .env uvicorn app.proxy:build_app --factory --port 11434
   ```
4. query it:
   ```sh
   # chat, blocking
   curl http://localhost:11434/api/chat -d '{"model":"qwen3","messages":[{"role":"user","content":"/dask how to parallelize a groupby"}],"stream":false}'

   # generate, blocking
   curl http://localhost:11434/api/generate -d '{"model":"qwen3","prompt":"/dask how to parallelize a groupby","stream":false}'

   # chat, streaming (NDJSON, one token per line)
   curl http://localhost:11434/api/chat -d '{"model":"qwen3","messages":[{"role":"user","content":"/dask how to parallelize a groupby"}],"stream":true}'
   ```

### Engines

The `ENGINE` variable, set in `.env` like the other variables, selects how a message is handled. The engines coexist in the code and are selected by configuration.

- `deterministic`: fixed rules, no LLM decides the routing. `/tag` for an indexed topic pulls the local RAG chunks, a URL reads that page, `/web <query>` searches the web; in all three the retrieved text and the question go to the model, which writes the answer. Anything else passes straight to the model
- `tool-agent`: an [any_agent](https://github.com/mozilla-ai/any-agent) orchestrator (tinyagent) decides which tools to use (`list_topics`, `retrieve`, `search_web`, `visit_webpage`). Their docstrings are richer than usual on purpose: any_agent passes each tool's docstring to the LLM as its description, so the docstring is what guides the model's tool choice. With `SHOW_TOOL_TRACE` on, a progress line is streamed to the IDE before each tool runs, so the chat is not frozen while the agent works (the final answer still arrives in one block)
- `agent-as-tool`: the `tool-agent` orchestrator plus a `write_code` tool that delegates to a coder sub-agent (the agent-as-tool pattern). The coder runs on `CODER_MODEL`, is grounded on the documentation the orchestrator passes it (and can `retrieve` more), and its code is checked before being returned: a deterministic gate (syntax, ruff signal) always, plus an opt-in reviewer sub-agent (`REVIEW`, `REVIEWER_MODEL`) that critiques correctness and grounding, with one revision round. The reviewer is off by default: on a small local model it flags everything (no discriminating signal, see [benchmark/reviewer.md](benchmark/reviewer.md)), so the deterministic gate is the local safety net; enable it with a capable model. A full `multi-agent` mode (peer agents with handoff) is a later phase

Which `.env` parameters each engine uses:

- all engines: `ENGINE`, `OLLAMA_URL`, `MODEL`, `EMBED_MODEL` and `TOP_K` (RAG retrieval); `HISTORY` sizes the conversation window (the agents use the prior turns, `deterministic` routes on the last message only). `MODEL` default `llama3.2:3b`: for the agents it is the orchestrator, the best small local model that delegates reliably via `/v1` (benchmarked); for `deterministic` (generation) `qwen2.5` or `coding` give more grounded answers (benchmarked), while `llama3.2:3b` is ~4x faster with slightly lower quality
- `deterministic` also: `CONTEXT_LENGTH` (generation `num_ctx`); set `MODEL=coding` for the coding persona
- `tool-agent` also: `SHOW_TOOL_TRACE`
- `agent-as-tool` also: `CODER_MODEL`, `REVIEW`, `REVIEWER_MODEL`, `SHOW_TOOL_TRACE`

`MAX_WORDS`, `OVERLAP`, `RESET`, `COLLECTION`, `DOCS_FOLDER` are used only by the indexing script (`scripts.document_manager.storage`), not by the running engine.

The choices above (embedder and chunk size for retrieval, the orchestrator model and the malformed-output guard, the deterministic-engine model trade-offs) are backed by reproducible measurements in [benchmark/README.md](benchmark/README.md): a page per benchmark plus the harness that regenerates them.

### OpenAI-compatible

The proxy also exposes the OpenAI-compatible `/v1` endpoints, passed through to Ollama, so an OpenAI client works against it:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
resp = client.chat.completions.create(
    model="qwen3",
    messages=[{"role": "user", "content": "Who wrote The Betrothed?"}],
)
print(resp.choices[0].message.content)
```

The `/tag` routing and RAG apply only to the Ollama-native `/api/chat` and `/api/generate`; the `/v1` endpoints are a plain pass-through for OpenAI compatibility.

### Continue (VS Code) setup

The [Continue](https://www.continue.dev/) extension speaks the Ollama-native API, so pointing it at the proxy (port `11434`, the Ollama default `apiBase`) lets it inherit the `/tag` routing and RAG. Add the model to `~/.continue/config.json`:

```json
{
  "models": [
    {
      "title": "Coding",
      "model": "coding",
      "provider": "ollama",
      "apiBase": "http://localhost:11434"
    }
  ]
}
```

With the proxy running, select `Coding` in the Continue chat and prefix a message with a known `/tag` to pull the local RAG chunks.

## Project structure

```
custom-ai-agents/
  app/  # FastAPI app and the blocks it manages
    proxy.py  # FastAPI app mimicking the Ollama API, uvicorn entrypoint
    router.py  # Router: selects the engine from the ENGINE parameter
    prompts.py  # load_prompt: read a prompt from prompts/
    engine/  # message-handling strategies, coexisting and selected by ENGINE
      base.py  # Engine interface: handle(message)
      deterministic.py  # DeterministicEngine: /tag, url, /web, else rules
      tool_agent.py  # ToolAgentEngine: an any_agent orchestrator picks the tools
    ag/  # augmented generation: local indexed knowledge sources
      base.py  # Retriever interface: list_topics(), retrieve(topic, query)
      chroma_db.py  # ChromaDb(Retriever): read side + indexing
    tools/  # live/external actions
      web_browsing.py  # WebBrowser: search_web, visit_webpage
  scripts/  # lean entrypoints calling app/
    document_manager/  # indexing and debug scripts
  prompts/  # prompt templates in markdown, loaded per engine
  tests/  # tests (pytest)
  data/  # local data
    chroma_db/  # persisted ChromaDB (ignored, only a versioned placeholder)
    documents/  # RAG corpus (only the README is versioned)
  modelfiles/
    Modelfile  # custom model with system prompt
  pyproject.toml  # dependencies + ruff/pyright/pytest config
  Makefile  # sync, test, lint, format, typecheck
```

## Development

```sh
uv sync  # install dependencies
make test  # run unit tests
make lint  # ruff check
make format  # ruff format
make typecheck  # pyright
```

## Blog post

- [POST.it.md](POST.it.md) (Italian)
- [POST.en.md](POST.en.md) (English)

## License

This repo is released under the MIT license. See [LICENSE](LICENSE) for details.
