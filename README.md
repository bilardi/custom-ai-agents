# Custom AI Agents

An app that mimics the Ollama API so it can be used from any Ollama-compatible IDE extension, adding `/tag` routing and a local RAG over ChromaDB.

## Prerequisites

- [Ollama](https://ollama.com/download) with a pulled model (e.g. `qwen3`)
- Python 3.13
- [uv](https://docs.astral.sh/uv/)

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
