# Multi-agent benchmark: handoff routing

The `multi-agent` engine is a triage agent that **hands off control** to a
specialist (`python_expert` or `aws_expert`), via the OpenAI Agents SDK (not
tinyagent, which has no handoff). Handoff is control transfer, unlike the consult
of `agent-as-tool`. This measures whether the triage routes to the right
specialist, and compares a small vs a capable local model.

## Method

Two requests with a known target specialist, run N=5 per model. Metric: the
share of runs where the run ends on the expected specialist (`RunResult.last_agent`).

| case | request | expected specialist |
|---|---|---|
| python | "Write a Python function to reverse a string." | python_expert |
| aws | "How do I create an S3 bucket with the AWS CLI?" | aws_expert |

Handoff relies on the model emitting a correct handoff tool-call; a small model
that leaks or mis-formats tool-calls routes poorly. Both specialists run on the
same `MODEL` (one model in VRAM per run), reached via `/v1`.

## Results (N=5)

| model | routing accuracy | note |
|---|---|---|
| llama3.2:3b | 60% (6/10) | often fails to hand off (the run ends on `triage`), especially AWS (2/5) |
| qwen2.5 | 90% (9/10) | reliable handoff (python 5/5, aws 4/5); one AWS run stayed on `triage` |

Conclusion: `qwen2.5` hands off reliably (90%); `llama3.2:3b` fails the control
transfer about 40% of the time (the run ends on `triage` without a valid handoff
tool-call). Handoff depends on reliable tool-calling, the same capability wall as
the orchestrator (delegation) and the reviewer: multi-agent works locally only
with a capable model, at the usual VRAM and latency cost. On the small default
model it is demonstrative, not dependable.

## Reproduce

```sh
MODEL=llama3.2:3b BENCH_RUNS=5 OLLAMA_URL=http://127.0.0.1:11435 \
    uv run python -m scripts.benchmark.multi_agent
MODEL=qwen2.5 BENCH_RUNS=5 OLLAMA_URL=http://127.0.0.1:11435 \
    uv run python -m scripts.benchmark.multi_agent
```

Requires the `multi-agent` dependency group (`uv sync --group multi-agent`) and
the chosen `MODEL`. Per-run routing in `benchmark/runs/multi_agent-<model>.md`.
