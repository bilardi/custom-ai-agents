"""Test the conversation benchmark: the HISTORY window carries a prior turn to the agent.

Non-deterministic (LLM), so it asserts the gap (HISTORY=2 reuses the prior snippet,
HISTORY=1 cannot); the rates are the measurement, discussed in benchmark/conversation.md.
"""

import pytest

from scripts.benchmark import conversation

pytestmark = pytest.mark.benchmark

MODEL = "llama3.2:3b"


def _reuse_rate(answers):
    return sum(conversation.reuses_snippet(a) for a in answers) / len(answers)


async def test_history_window_carries_prior_snippet(ollama_url, require_model, bench_runs):
    require_model(MODEL)
    require_model("nomic-embed-text")
    without_history = await conversation.run(1, bench_runs, MODEL, ollama_url)
    with_history = await conversation.run(2, bench_runs, MODEL, ollama_url)
    assert _reuse_rate(with_history) >= 0.6
    assert _reuse_rate(without_history) <= 0.2
