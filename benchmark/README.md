# Benchmarks

Reproducible measurements behind the design choices summarised in the main
[README](../README.md): which embedder and chunk size ground retrieval, which
local model delegates reliably as the agent orchestrator, and how the models
compare for deterministic RAG generation. These pages hold the detail that is
kept deliberately concise in the main README.

## Method

A local model is evaluated like an ML component: over N runs, not a single
sample. A single run is misleading; the metric is a rate over N (default 5).
Agents reach Ollama through its OpenAI-compatible `/v1` endpoint, where
tool-calling is far more reliable than via the native provider.

Two kinds of measurement:

- retrieval (grounding) is deterministic: the same embeddings give the same
  ranks, so [grounding.md](grounding.md) is reproduced exactly by a regression test
- generation (deterministic engine) and orchestrator delegation depend on LLM
  sampling: [deterministic.md](deterministic.md) and [orchestrator.md](orchestrator.md)
  are measurement tests that record rates and assert the committed conclusion, not
  byte-identical output

## The benchmarks

- [grounding.md](grounding.md): embedder, chunk size and overlap for retrieval; winner `nomic-embed-text` + `MAX_WORDS=500` + `OVERLAP=0`
- [orchestrator.md](orchestrator.md): which model delegates reliably to `write_code` via `/v1`; winner `llama3.2:3b` + the malformed-output guard
- [deterministic.md](deterministic.md): RAG generation quality across `qwen2.5`, `coding`, `llama3.2:3b`, `coding-llama`

## Environment

- GPU: RTX 4050 Laptop, 6 GB VRAM (one model for all agent roles fits; distinct orchestrator + coder models do not)
- Ollama reached at `OLLAMA_URL` (the reference runs used `http://127.0.0.1:11435`), agents via `/v1`
- corpus: the dask docs under `data/documents/dask` (not versioned; obtain them per [../data/documents/README.md](../data/documents/README.md)), indexed into topic `dask`

## Reproduce

The harness lives in `scripts/benchmark/` (runnable modules, like
`scripts/document_manager`); the pytest tests in `tests/scripts/benchmark/` drive
it and assert the conclusions. The tests are marked `benchmark` and deselected
from the default suite (like `integration`). Both harness and tests skip when
Ollama is unreachable or a required model is missing, and write the per-run
output to `benchmark/runs/`.

Prerequisite: the benchmarks need the dask corpus indexed, and neither the
documents nor the index are versioned. On a fresh clone, obtain the documents
(see [../data/documents/README.md](../data/documents/README.md)) and index them
once; grounding reindexes the folder itself, while deterministic and orchestrator
query the already-indexed `dask` topic:

```sh
DOCS_FOLDER=data/documents/dask COLLECTION=dask RESET=true \
    OLLAMA_URL=http://127.0.0.1:11435 uv run python -m scripts.document_manager.storage
```

```sh
# run a benchmark standalone (from the repo root)
MODEL=qwen2.5 BENCH_RUNS=5 OLLAMA_URL=http://127.0.0.1:11435 \
    uv run python -m scripts.benchmark.deterministic
# grounding is deterministic: no BENCH_RUNS
OLLAMA_URL=http://127.0.0.1:11435 uv run python -m scripts.benchmark.grounding

# or run them as tests (asserts the conclusions), opt-in marker
OLLAMA_URL=http://127.0.0.1:11435 uv run pytest tests/scripts/benchmark -m benchmark
```

Required models per benchmark:

- grounding: `nomic-embed-text`
- deterministic: `nomic-embed-text` and each of `qwen2.5`, `coding`, `llama3.2:3b`, `coding-llama` (a model absent from Ollama is skipped)
- orchestrator: `nomic-embed-text`, `qwen2.5`, `llama3.2:3b`

`coding` and `coding-llama` are custom models; see the model recipes in
[deterministic.md](deterministic.md). Some rows in the pages come from a wider
one-off exploration (the 8B and `qwen3` orchestrators, the qwen3 embedder, the
chunk-size and overlap sweep) and are documented but not reproduced by the tests;
each page marks which rows are test-backed.

## Layout

- `scripts/benchmark/helpers.py`: shared metrics, retrieval and Ollama probing (typed module)
- `scripts/benchmark/{deterministic,orchestrator,grounding}.py`: runnable harness, one per benchmark
- `tests/scripts/benchmark/`: pytest that drive the harness and assert the conclusions
- `benchmark/*.md`: this page and one write-up per benchmark
- `benchmark/runs/`: per-run output written by the last run
