# Deterministic engine benchmark: RAG generation quality

Test request (identical for all): **`/dask how to parallelize a groupby`**
(engine `deterministic`: `/tag` -> RAG -> `retrieve` chunk -> prompt ->
generation). EMBED_MODEL nomic-embed-text, CONTEXT_LENGTH 4096, TOP_K 3, via
`/v1`. 10 runs per model (two recorded sessions of 5, pooled).

Reproduced by `scripts.benchmark.deterministic`, which writes the per-run answers
and these aggregates to `benchmark/runs/deterministic-<model>.md`.

## Results (10 runs)

| model | syntax_ok | grounded | from_pandas | over_eng | latency |
|---|---|---|---|---|---|
| qwen2.5 | 7/10 | 9/10 | 0/10 | 1/10 | ~29s |
| coding (qwen2.5 + SYSTEM) | 9/10 | 10/10 | 0/10 | 4/10 | ~32s |
| llama3.2:3b | 9/10 | 7/10 | 0/10 | 9/10 | ~6s |
| coding-llama (llama3.2:3b + SYSTEM) | 5/10 | 5/10 | 2/10 | 7/10 | ~7s |

All columns are per-run signals the script computes over the answers (`x/10` =
runs matching): `syntax_ok` = all code blocks pass `ast.parse`; `grounded` = uses
the docs' `groupby("Origin")` example; `from_pandas` = builds an example DataFrame
via `dd.from_pandas` (a real API) instead of grounding on the retrieved example (a
generic answer); `over_eng` = reaches for the `delayed` API for a simple groupby.

## Conclusions

- **coding FROM qwen2.5 >> coding-llama**: the same persona (`SYSTEM`) on a llama3.2:3b base is worse: less grounded (5/10 vs 10/10), more generic answers via `from_pandas` (2/10 vs 0/10), over-engineers more (7/10 vs 4/10), worse syntax (5/10 vs 9/10). If `coding` is needed, it must stay **FROM qwen2.5**
- **bare qwen2.5 vs `coding`**: roughly even. `coding` is more robust on syntax (9/10 vs 7/10) but tends to over-engineer (4/10 vs 1/10 `delayed`); both strongly grounded (10/10, 9/10). The persona helps syntax, not simplicity. This overturns the earlier single-sample impression ("bare is better")
- **qwen2.5-based (qwen2.5 / coding) > llama-based** on quality: more grounded (9-10/10 vs 7/10 llama, 5/10 coding-llama) and simpler (`over_eng` 1-4/10 vs 9/10 llama), but **llama-based is ~5x faster** (~6-7s vs ~29-32s). Note: `syntax_ok` alone would mislead (llama 9/10 = coding); `grounded` and `over_eng` reveal the gap

## Recommendation for the deterministic engine

- quality: `MODEL=qwen2.5` (or `coding` for style + syntactic robustness, always on a qwen2.5 base)
- speed: `MODEL=llama3.2:3b` (~5x faster; grounds less and over-engineers more, but usable)
- `coding` stays **FROM qwen2.5**; `coding-llama` dropped
- the default `MODEL=llama3.2:3b` is for the **agents** (delegation); for the deterministic engine it is a separate choice (quality vs speed)

## Model recipes

The two custom models share the same `SYSTEM` (see `modelfiles/Modelfile` for
the full text); they differ only in the base:

```sh
# coding: quality base, kept as the deterministic coding persona
ollama create coding -f modelfiles/Modelfile          # FROM qwen2.5

# coding-llama: same SYSTEM on the fast base, benchmarked and dropped
# (a Modelfile identical to modelfiles/Modelfile but "FROM llama3.2:3b")
ollama create coding-llama -f <that-modelfile>
```
