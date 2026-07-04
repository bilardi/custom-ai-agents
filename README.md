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

Pull the base model, and optionally create the `coding` model (a coding-assistant persona defined in `ollama/Modelfile`):

```sh
ollama pull qwen2.5
ollama create coding -f ollama/Modelfile
```

### End-to-end test

| Variable | Default | Controls |
|---|---|---|
| `ENGINE` | `deterministic` | which engine handles messages (later `tool-agent`, `multi-agent`) |
| `MODEL` | `qwen3` | Ollama model used for generation |
| `EMBED_MODEL` | `qwen3` | Ollama model used for embeddings (must match the index) |
| `OLLAMA_URL` | `http://localhost:11434` | base URL of the Ollama server |
| `TOP_K` | `3` | number of RAG chunks retrieved per query |
| `MAX_WORDS` | `300` | chunk size in words (indexing) |
| `CONTEXT_LENGTH` | unset | generation context window (Ollama `num_ctx`); lower = faster |
| `COLLECTION` | `dask` | topic to index (storage script) |
| `DOCS_FOLDER` | `data/documents/dask` | folder to index (storage script) |

Copy the template and edit your values:

```sh
cp .env.example .env
```

To use the coding-assistant persona, set `MODEL=coding` in `.env`.

End-to-end test (Ollama must be running):

1. index a topic:
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

With the `deterministic` engine the routing only chooses the context for the model: `/tag` for a known topic pulls the local RAG chunks, a URL in the message reads that page, `/web <query>` searches the web. In all three cases the retrieved text and the question are sent to the Ollama model, which writes the answer. Anything else goes straight to the model, which answers from its own knowledge.

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
    engine/  # message-handling strategies, coexisting and selected by ENGINE
      base.py  # Engine interface: handle(message)
      deterministic.py  # DeterministicEngine: /tag, url, /web, else rules
    ag/  # augmented generation: local indexed knowledge sources
      base.py  # Retriever interface: list_topics(), retrieve(topic, query)
      chroma_db.py  # ChromaDb(Retriever): read side + indexing
    tools/  # live/external actions
      web_browsing.py  # WebBrowser: search_web, visit_webpage
  scripts/  # lean entrypoints calling app/
    document_manager/  # indexing and debug scripts
  tests/  # tests (pytest)
  data/  # local data
    chroma_db/  # persisted ChromaDB (ignored, only a versioned placeholder)
    documents/  # RAG corpus (only the README is versioned)
  ollama/
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
