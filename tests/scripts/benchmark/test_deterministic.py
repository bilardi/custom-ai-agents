"""Test the deterministic-engine benchmark: measurement over N runs per model.

LLM generation is non-deterministic, so this asserts liveness and lets the
harness record the per-run answers to benchmark/runs/. See benchmark/deterministic.md.
"""

import pytest

from scripts.benchmark import deterministic

pytestmark = pytest.mark.benchmark

MODELS = ["qwen2.5", "coding", "llama3.2:3b", "coding-llama"]


@pytest.mark.parametrize("model", MODELS)
async def test_deterministic_quality(model, ollama_url, require_model, bench_runs):
    require_model("nomic-embed-text")
    require_model(model)
    results = await deterministic.run(model, bench_runs, ollama_url)
    assert len(results) == bench_runs
    assert all(answer for answer, _ in results)
