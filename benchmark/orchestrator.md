# Orchestrator benchmark: reliable delegation

Test question: "write dask code to parallelize a groupby aggregation on a
dataframe". Engine `agent-as-tool`, all roles on the same model, provider
`openai` pointed at Ollama `/v1`. Metric over N runs: how often the orchestrator
**delegates** to `write_code`, how often the output is **malformed** (a tool
call emitted as text), and latency.

## Results (via /v1)

| orchestrator | delegates | malformed | latency | note |
|---|---|---|---|---|
| qwen2.5 | 2/5 | 0/5 | 20-102s (variable) | format always ok, delegates little (~40%) |
| llama3.2:3b | 4/5 | 1/5 | ~23s (steady) | delegates ~80%, fast; 1 run leaked a tool call as text |
| llama3.1:8b | 3/5 | 3/5 | 4-123s | via /v1 it delegates but the `<|python_tag|>` token leaks into the text (malformed) and it is slow |
| hermes3:8b | 0/5 | 0/5 | 4-27s | never delegates (asks for the task or answers by itself) |
| qwen3 (thinking) | reliable | 0 | minutes (5-10) | slow |

Ranking (via /v1): **llama3.2:3b** is the best fast trade-off (80% delegation,
~23s, 20% malformed); qwen2.5 never gets the format wrong but delegates little
(40%); qwen3 is reliable but slow. The **8B models are worse than the small
ones** here: llama3.1 leaks its native format (`<|python_tag|>`), hermes3 never
delegates. Against the prior "bigger = steadier": what matters is the
compatibility of the model's *tool-call format* with the stack, not size alone.

The guarded-path numbers for `qwen2.5` and `llama3.2:3b` are reproduced by
`scripts.benchmark.orchestrator` (see the guard section below); this table is the
no-guard exploration (all rows N=5), documented and not re-run by the test.

## Orchestrator prompt (agent_as_tool)

Tested a "decision-first" variant (code rule first, imperative) versus the original, N=5:

| prompt | qwen2.5 (delegates/malformed) | llama3.2:3b (delegates/malformed) |
|---|---|---|
| original | 2/5, 0/5 | 4/5, 1/5 |
| decision-first | 1/5, 1/5 | 3/5, 3/5 |

The variant **makes both worse** (malformed especially). Dropped, kept the
original. Lesson: on small models a more "imperative/terse" prompt does not help
delegation and increases malformed tool calls. This comparison is documented
exploration, not re-run by the test.

## Anti-malformed guard (the turning point)

The main weakness of llama3.2:3b was the ~20% malformed output (a tool call as
text). Added a guard in the engine: if the orchestrator's final answer contains
a leaked tool call (`<|python_tag|>`, `{"name":`, `write_code(`), it is
**regenerated once**. Guarded-path results (N=10, the path the harness runs):

| config | delegates | malformed | latency |
|---|---|---|---|
| llama3.2:3b (no guard, N=5 exploration) | 4/5 | 1/5 | ~23s |
| llama3.2:3b (with guard) | 9/10 | 1/10 | ~24s |
| qwen2.5 (with guard) | 5/10 | 0/10 | 20-102s (variable) |

The guard roughly halves the malformed rate (regenerating once): from ~20%
without it to ~10% with it. It does **not** eliminate it: over 10 runs one still
slipped through (1/10, the single regeneration also came back malformed). Net:
**llama3.2:3b + /v1 + guard = fast (~24s) and reliably delegating (~90%)**, with
malformed low but not zero. Adopted default: `MODEL=llama3.2:3b` for all roles.
`scripts.benchmark.orchestrator` reproduces this guarded path (its test asserts
llama3.2:3b delegates in at least 60% of runs with a malformed rate <= 20%); the
"no guard" row is documented, not re-run.

## Notes

- evaluating a model on a single run is misleading: you need a rate over N (as for an ML component). Over N=5 llama3.2:3b (80% delegation, ~23s) beats qwen2.5 (40%), contrary to how single runs looked
- `/v1` (the OpenAI format) is necessary: with the native provider qwen2.5 delegated less and llama emitted text
