"""Benchmark orchestrator delegation reliability via /v1 with the guard.

Runs the agent-as-tool engine (all roles on the same model, reached through
Ollama's /v1 endpoint, with the malformed-output guard) N times and measures how
often the orchestrator delegates to write_code and how often the final answer
leaks a tool call as text. Writes the per-run output to
benchmark/runs/orchestrator-<model>.md. Run from the repo root:

    MODEL=llama3.2:3b BENCH_RUNS=5 OLLAMA_URL=http://127.0.0.1:11435 \
        uv run python -m scripts.benchmark.orchestrator
"""

import asyncio
import logging
import os
import time
from pathlib import Path

from httpx import ASGITransport, AsyncClient

# reuse the engine's own predicate so the benchmark measures exactly what the
# guard treats as malformed (no drift from duplicating the markers)
from app.engine.tool_agent import _is_malformed  # pyright: ignore[reportPrivateUsage]
from app.proxy import build_app
from scripts.benchmark.helpers import write_report

logger = logging.getLogger("benchmark.orchestrator")

PROMPT = "write dask code to parallelize a groupby aggregation on a dataframe"
DELEGATION_MARK = "> writing code..."
RUNS_DIR = Path("benchmark/runs")

Run = tuple[bool, bool, float, str]


async def run(model: str, runs: int, ollama_url: str) -> list[Run]:
    """Run the agent-as-tool engine `runs` times for `model`; write and return the runs.

    Each run is (delegated, malformed, latency, content).
    """
    os.environ.update(
        ENGINE="agent-as-tool",
        MODEL=model,
        CODER_MODEL=model,
        REVIEWER_MODEL=model,
        EMBED_MODEL="nomic-embed-text",
        OLLAMA_URL=ollama_url,
        SHOW_TOOL_TRACE="1",
    )
    app = build_app()
    outcomes: list[Run] = []
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t", timeout=600) as client:
        for _ in range(runs):
            start = time.time()
            response = await client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": PROMPT}], "stream": False},
            )
            content = response.json()["message"]["content"]
            elapsed = time.time() - start
            outcomes.append((DELEGATION_MARK in content, _is_malformed(content), elapsed, content))
    _report(model, outcomes)
    return outcomes


def delegation_rate(outcomes: list[Run]) -> float:
    """Return the fraction of runs where the orchestrator delegated to write_code."""
    return sum(1 for delegated, _, _, _ in outcomes if delegated) / len(outcomes)


def malformed_count(outcomes: list[Run]) -> int:
    """Return the number of runs whose final answer leaked a tool call as text."""
    return sum(1 for _, bad, _, _ in outcomes if bad)


def _report(model: str, outcomes: list[Run]) -> Path:
    """Write the per-run output and a summary to benchmark/runs, returning the path."""
    rate = delegation_rate(outcomes)
    malformed = malformed_count(outcomes)
    summary = f"prompt: `{PROMPT}`\n\ndelegation {rate:.0%}, malformed {malformed}/{len(outcomes)}"
    details = [
        (f"run {i} (delegated={delegated}, malformed={bad}, {elapsed:.0f}s)", content)
        for i, (delegated, bad, elapsed, content) in enumerate(outcomes, start=1)
    ]
    path = RUNS_DIR / f"orchestrator-{model.replace(':', '_')}.md"
    write_report(path, f"orchestrator - {model}", [("summary", summary), *details])
    return path


def main() -> None:
    """Run the benchmark for MODEL over BENCH_RUNS runs and log the summary."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", force=True)
    model = os.getenv("MODEL", "llama3.2:3b")
    runs = int(os.getenv("BENCH_RUNS", "5"))
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    outcomes = asyncio.run(run(model, runs, ollama_url))
    logger.info(
        "%s: delegation %.0f%%, malformed %d/%d (see benchmark/runs)",
        model,
        delegation_rate(outcomes) * 100,
        malformed_count(outcomes),
        len(outcomes),
    )


if __name__ == "__main__":
    main()
