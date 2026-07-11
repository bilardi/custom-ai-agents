# Reviewer benchmark: catch rate vs false positives

The reviewer sub-agent (`REVIEWER_MODEL`) critiques the coder's output for
correctness and grounding. On a small local model it may miss invented APIs that
are syntactically valid (a syntax gate cannot catch them). This measures whether
it catches them, and whether it wrongly flags correct code.

Grounding is semantic, not deterministic, so it is judged by the reviewer (given
the retrieved context and a prompt), not by a token check: a token match confuses
"different from the chunk" with "wrong" and penalises valid variations.

## Method

A fixed task and documentation context (the dask groupby example), with four
labeled code samples. Each is reviewed N runs (default 10); the metric is how
often the reviewer flags it (a non-empty critique). Since the reviewer is an LLM,
this is a measurement over N, not a single sample.

| case | code | expected | measures |
|---|---|---|---|
| invented-api | `@dd(delayed=True)` decorator (dd is a module, not a decorator) | flag | catch rate (higher better) |
| good-grounded | the context's `groupby("Origin").DepDelay.mean().compute()` | OK | false-positive rate (lower better) |
| valid-variation | correct but different: `groupby(...).agg({"DepDelay": "mean"})` | OK | false-positive rate |
| generic-ungrounded | correct but ignores the example: a synthetic df via `dd.from_pandas` | not scored | grounding-strictness call, reported for discussion |

The `generic-ungrounded` case is **correct code** (`dd.from_pandas` is a real API,
`groupby` is in the context); it just does not use the retrieved example. Whether
that should be flagged is a product decision (is grounding a hard requirement?),
so it is reported separately, not scored as a failure.

## Reproduce

```sh
REVIEWER_MODEL=llama3.2:3b BENCH_RUNS=10 OLLAMA_URL=http://127.0.0.1:11435 \
    uv run python -m scripts.benchmark.reviewer
```

Requires `llama3.2:3b` (or the chosen `REVIEWER_MODEL`). Per-run output in
`benchmark/runs/reviewer-<model>.md`.

## Results

Evaluated as an A/B: the current free-form prompt (baseline) vs a checklist
prompt, on the same fixed set. A checklist is kept only if it raises the catch
rate without raising the false-positive rate.

Two axes: the reviewer model (`llama3.2:3b` vs the more capable local `qwen2.5`)
and the prompt (free-form baseline vs checklist). All local (the benchmark loads
one model at a time, so qwen2.5 fits 6 GB).

| model | prompt | catch (invented) | false positives (correct) | generic flagged |
|---|---|---|---|---|
| llama3.2:3b | baseline (free-form) | 100% (10/10) | 100% (10/10) | 100% (10/10) |
| llama3.2:3b | checklist | 100% (10/10) | 100% (20/20) | 80% (8/10) |
| qwen2.5 | baseline (free-form) | 90% (9/10) | 45% (9/20) | 0% (0/10) |
| qwen2.5 | checklist | 60% (6/10) | 0% (0/20) | 0% (0/10) |

Baseline finding (llama3.2:3b): the reviewer flags **everything**. The 100% catch
is meaningless next to 100% false positives: a reviewer that always reports a
problem equals "always revise", with no discriminating signal. Inspecting the raw
output shows it is not a parsing artifact but **invented critiques**: on correct
code it hallucinates wrong problems (claims `dask.dataframe` should be aliased
`da` not `dd`; misreads a non-existent `rdf` variable; calls the valid
`groupby(...).agg({...})` invalid). And the catch is **blind**: on the invented
`@dd(delayed=True)` it did not identify the real bug, it invented irrelevant
problems and even "fixed" it to another wrong form. So both catch and false
positives come from the same cause: a 3B model over-critiques and its Dask facts
are wrong. A checklist can trim over-critique but cannot inject correct domain
knowledge, so the qwen2.5 row tests whether a more capable local model is the
real lever.

Deployment note: `REVIEWER_MODEL=qwen2.5` alongside a llama3.2:3b
orchestrator/coder is two models (~6.7 GB) and OOMs on 6 GB; all-qwen2.5 fits but
the orchestrator delegates less (~50%). The benchmark isolates reviewer capability;
using a better reviewer in the full flow is a separate VRAM/delegation trade-off.

Conclusion: the dominant lever is the **model**, not the prompt. `llama3.2:3b`
flags everything (100% false positives) under both prompts: it is capability-bound
and no prompt fixes it. `qwen2.5` discriminates; on it the checklist is a
precision/recall knob: it removed the false positives (including the valid `.agg`
variation, 9/10 -> 0/10) but lowered the catch (90% -> 60%, letting invented APIs
slip through). Neither qwen2.5 prompt hits the sweet spot: baseline favors recall
(catch 90%, false positives 45%), checklist favors precision (catch 60%, false
positives 0%). Against the pre-set rule (keep the checklist only if it raises catch
without worsening false positives), the checklist is not adopted.

So an effective reviewer needs a `qwen2.5`-class local model, not a better prompt
on a 3B. But `qwen2.5` as `REVIEWER_MODEL` is not free on 6 GB (OOM beside a
llama orchestrator, or all-qwen2.5 with weaker delegation). The reviewer is
therefore capability-bound: useful only with a model this project cannot always
afford to run locally alongside the rest.

Decision: the reviewer is made **opt-in** (`REVIEW`, default off). On the default
local model it is dead weight (it always flags), so the coder's deterministic gate
(syntax/ruff) carries the local safety net; the reviewer is enabled only with a
capable `REVIEWER_MODEL`.
