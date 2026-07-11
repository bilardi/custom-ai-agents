# Conversation benchmark: does the HISTORY window reach the agent?

`HISTORY` sizes the trailing conversation window passed to the engine (default 1
= last message only). Unit tests prove the plumbing (the proxy slices the window,
the agent prompt renders the transcript). This measures the behavior end-to-end:
with a larger window, does the agent actually use a prior turn?

## Method

A fixed first turn (a groupby snippet as the assistant reply) and a second turn
that says "turn that snippet into a reusable function". `that snippet` is an
anaphora: it resolves only if the prior turn is in the window. Engine
`agent-as-tool`, `MODEL=llama3.2:3b`, turn 2 run N=5 per `HISTORY` value. Metric:
how often the answer reuses the prior snippet (its distinctive `groupby("Origin")`
/ `DepDelay`), and how often it defines a function.

## Results (N=5)

| HISTORY | reuses prior snippet | defines a function |
|---|---|---|
| 1 (last message only) | 0/5 | 3/5 |
| 2 | 5/5 | 5/5 |

## Conclusion

With `HISTORY=2` the agent has the prior turn and resolves "that snippet" every
time (5/5), wrapping the retrieved `groupby("Origin")` code in a function. With
`HISTORY=1` it sees only "turn that snippet into a function", cannot know which
snippet, and writes a generic function instead (0/5 reuse). The window reaches
the agent and it uses it: multi-turn works once `HISTORY` is raised.

Cost: a larger window means more tokens per call, so it needs a larger `MODEL`
(small models degrade tool-calling on long context) and a bigger `CONTEXT_LENGTH`.
Default stays 1; raise `HISTORY` when you move to a capable model.

## Reproduce

```sh
MODEL=llama3.2:3b BENCH_RUNS=5 OLLAMA_URL=http://127.0.0.1:11435 \
    uv run python -m scripts.benchmark.conversation
```

Requires `llama3.2:3b` and `nomic-embed-text`. Per-run output in
`benchmark/runs/conversation-history<N>.md`.
