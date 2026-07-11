"""Test the multi-agent routing benchmark (needs the OpenAI Agents SDK + a running Ollama).

Measurement (LLM handoff is non-deterministic); asserts the harness runs each case
N times. Routing accuracy is the measurement, discussed in benchmark/multi_agent.md.
"""

import pytest

from scripts.benchmark import multi_agent

pytestmark = pytest.mark.benchmark

MODEL = "llama3.2:3b"


async def test_multi_agent_runs_all_cases(ollama_url, require_model, bench_runs):
    pytest.importorskip("agents")
    require_model(MODEL)
    results = await multi_agent.run(MODEL, bench_runs, ollama_url)
    assert set(results) == {case["name"] for case in multi_agent.CASES}
    assert all(len(outcomes) == bench_runs for outcomes in results.values())
