"""Benchmark the deterministic engine's RAG generation quality for a model.

Runs the same request through the deterministic engine N times and, per run,
records the answer and its latency; from each answer it computes reproducible
per-run signals (syntax_ok, grounded, from_pandas, over_eng). Writes the per-run
answers and the aggregate to benchmark/runs/deterministic-<model>.md. Run from
the repo root:

    MODEL=qwen2.5 BENCH_RUNS=5 OLLAMA_URL=http://127.0.0.1:11435 \
        uv run python -m scripts.benchmark.deterministic
"""

import asyncio
import logging
import os
import time
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from app.proxy import build_app
from scripts.benchmark.helpers import (
    generic_from_pandas,
    grounded,
    over_engineered,
    syntax_ok,
    write_report,
)

logger = logging.getLogger("benchmark.deterministic")

PROMPT = "/dask how to parallelize a groupby"
RUNS_DIR = Path("benchmark/runs")

# (answer, latency in seconds); the per-run signals are derived from the answer.
Result = tuple[str, float]


async def run(model: str, runs: int, ollama_url: str) -> list[Result]:
    """Run the deterministic engine `runs` times for `model`; write and return the results."""
    os.environ.update(
        ENGINE="deterministic",
        MODEL=model,
        EMBED_MODEL="nomic-embed-text",
        OLLAMA_URL=ollama_url,
        CONTEXT_LENGTH="4096",
        TOP_K="3",
    )
    app = build_app()
    results: list[Result] = []
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t", timeout=600) as client:
        for _ in range(runs):
            start = time.time()
            response = await client.post(
                "/api/chat",
                json={"messages": [{"role": "user", "content": PROMPT}], "stream": False},
            )
            content = response.json()["message"]["content"]
            results.append((content, time.time() - start))
    _report(model, results)
    return results


def aggregate(results: list[Result]) -> dict[str, str]:
    """Return the aggregate per-run signals over the results, each as 'x/n' (or a latency)."""
    n = len(results)
    ok = sum(1 for answer, _ in results if syntax_ok(answer) is True)
    grd = sum(1 for answer, _ in results if grounded(answer))
    fp = sum(1 for answer, _ in results if generic_from_pandas(answer))
    oe = sum(1 for answer, _ in results if over_engineered(answer))
    avg = sum(latency for _, latency in results) / n
    return {
        "runs": str(n),
        "syntax_ok": f"{ok}/{n}",
        "grounded": f"{grd}/{n}",
        "from_pandas": f"{fp}/{n}",
        "over_eng": f"{oe}/{n}",
        "avg latency": f"{avg:.0f}s",
    }


def _run_heading(index: int, answer: str, latency: float) -> str:
    """Return the per-run heading with its derived signals."""
    return (
        f"run {index} (syntax_ok={syntax_ok(answer)}, grounded={grounded(answer)}, "
        f"from_pandas={generic_from_pandas(answer)}, over_eng={over_engineered(answer)}, "
        f"{latency:.0f}s)"
    )


def _report(model: str, results: list[Result]) -> Path:
    """Write the per-run answers and the aggregate to benchmark/runs, returning the path."""
    metrics = aggregate(results)
    summary = f"prompt: `{PROMPT}`\n\n| metric | value |\n|---|---|\n" + "\n".join(
        f"| {key} | {value} |" for key, value in metrics.items()
    )
    details = [
        (_run_heading(i, answer, latency), answer)
        for i, (answer, latency) in enumerate(results, start=1)
    ]
    path = RUNS_DIR / f"deterministic-{model.replace(':', '_')}.md"
    write_report(path, f"deterministic - {model}", [("summary", summary), *details])
    return path


def main() -> None:
    """Run the benchmark for MODEL over BENCH_RUNS runs and log the aggregate."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", force=True)
    model = os.getenv("MODEL", "qwen2.5")
    runs = int(os.getenv("BENCH_RUNS", "5"))
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    results = asyncio.run(run(model, runs, ollama_url))
    logger.info("%s: %s (see benchmark/runs)", model, aggregate(results))


if __name__ == "__main__":
    main()
