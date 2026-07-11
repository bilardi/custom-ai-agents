"""Test the reviewer benchmark harness (measurement; needs a running Ollama).

Checks the harness plumbing (all cases run N times); the catch/false-positive
rates themselves are the measurement, discussed in benchmark/reviewer.md.
"""

import pytest

from scripts.benchmark import reviewer

pytestmark = pytest.mark.benchmark

MODEL = "llama3.2:3b"


async def test_reviewer_benchmark_runs_all_cases(ollama_url, require_model, bench_runs):
    require_model(MODEL)
    flags = await reviewer.run(MODEL, bench_runs, ollama_url)
    assert set(flags) == {case["name"] for case in reviewer.CASES}
    assert all(len(runs) == bench_runs for runs in flags.values())
