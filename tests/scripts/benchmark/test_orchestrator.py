"""Test the orchestrator benchmark: reliable delegation via /v1 with the guard.

LLM behavior is non-deterministic, so this asserts the committed conclusion
(llama3.2:3b delegates reliably with the guard) and lets the harness record the
per-run output to benchmark/runs/. The 8B and qwen3 rows of
benchmark/orchestrator.md are documented exploration, not reproduced here.
"""

import pytest

from scripts.benchmark import orchestrator

pytestmark = pytest.mark.benchmark

MODELS = ["qwen2.5", "llama3.2:3b"]
MIN_DELEGATION_RATE = 0.6
# the guard reduces but does not eliminate malformed output (see orchestrator.md)
MAX_MALFORMED_RATE = 0.2


@pytest.mark.parametrize("model", MODELS)
async def test_orchestrator_delegation(model, ollama_url, require_model, bench_runs):
    require_model(model)
    require_model("nomic-embed-text")
    outcomes = await orchestrator.run(model, bench_runs, ollama_url)
    assert len(outcomes) == bench_runs

    if model == "llama3.2:3b":
        rate = orchestrator.delegation_rate(outcomes)
        malformed_rate = orchestrator.malformed_count(outcomes) / len(outcomes)
        assert rate >= MIN_DELEGATION_RATE, f"delegation {rate:.0%}"
        assert malformed_rate <= MAX_MALFORMED_RATE, f"malformed {malformed_rate:.0%}"
