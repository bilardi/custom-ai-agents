"""Benchmark the HISTORY window: whether the agent reuses a prior-turn snippet.

Fixes a first turn (a groupby snippet as the assistant reply) and asks a second
turn to turn "that snippet" into a reusable function. Runs turn 2 N times per
HISTORY value and measures how often the answer reuses the prior snippet (its
distinctive groupby("Origin") / DepDelay). HISTORY=1 (last message only) cannot
resolve "that snippet"; HISTORY=2 gives the agent the prior turn. Writes
benchmark/runs/conversation-history<N>.md. Run from the repo root:

    MODEL=llama3.2:3b BENCH_RUNS=5 OLLAMA_URL=http://127.0.0.1:11435 \
        uv run python -m scripts.benchmark.conversation
"""

import asyncio
import logging
import os
from collections.abc import Callable
from pathlib import Path

from httpx import ASGITransport, AsyncClient

from app.proxy import build_app
from scripts.benchmark.helpers import write_report

logger = logging.getLogger("benchmark.conversation")

RUNS_DIR = Path("benchmark/runs")

USER1 = "Write Dask code to parallelize a groupby aggregation on a DataFrame."
SNIPPET_ANSWER = (
    "Here is the code:\n\n```python\n"
    "import dask.dataframe as dd\n\n"
    'ddf = dd.read_csv("nycflights/*.csv")\n'
    'result = ddf.groupby("Origin").DepDelay.mean().compute()\n'
    "print(result)\n```"
)
USER2 = "Now turn that snippet into a reusable function."

MESSAGES = [
    {"role": "user", "content": USER1},
    {"role": "assistant", "content": SNIPPET_ANSWER},
    {"role": "user", "content": USER2},
]


def reuses_snippet(answer: str) -> bool:
    """Return whether the answer carries over the prior snippet's distinctive API."""
    return 'groupby("Origin")' in answer or "DepDelay" in answer


def is_method(answer: str) -> bool:
    """Return whether the answer defines a function."""
    return "def " in answer


async def run(history: int, runs: int, model: str, ollama_url: str) -> list[str]:
    """Run turn 2 `runs` times with the given HISTORY; write and return the answers."""
    os.environ.update(
        ENGINE="agent-as-tool",
        MODEL=model,
        CODER_MODEL=model,
        EMBED_MODEL="nomic-embed-text",
        OLLAMA_URL=ollama_url,
        HISTORY=str(history),
    )
    app = build_app()
    answers: list[str] = []
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t", timeout=600) as client:
        for _ in range(runs):
            response = await client.post("/api/chat", json={"messages": MESSAGES, "stream": False})
            answers.append(response.json()["message"]["content"])
    _report(history, answers)
    return answers


def _rate(answers: list[str], predicate: Callable[[str], bool]) -> str:
    hits = sum(1 for answer in answers if predicate(answer))
    return f"{hits}/{len(answers)}"


def _report(history: int, answers: list[str]) -> Path:
    """Write the per-run answers and the reuse rate to benchmark/runs, returning the path."""
    summary = (
        f"turn 1 (fixed): `{USER1}` -> groupby snippet; turn 2: `{USER2}`\n\n"
        f"HISTORY={history}: reuses prior snippet {_rate(answers, reuses_snippet)}, "
        f"defines a function {_rate(answers, is_method)}"
    )
    details = [
        (f"run {i} (reuse={reuses_snippet(a)}, method={is_method(a)})", a)
        for i, a in enumerate(answers, start=1)
    ]
    path = RUNS_DIR / f"conversation-history{history}.md"
    write_report(path, f"conversation - HISTORY={history}", [("summary", summary), *details])
    return path


def main() -> None:
    """Run the HISTORY A/B (1 vs 2) over BENCH_RUNS runs and log the reuse rates."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", force=True)
    model = os.getenv("MODEL", "llama3.2:3b")
    runs = int(os.getenv("BENCH_RUNS", "5"))
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    for history in (1, 2):
        answers = asyncio.run(run(history, runs, model, ollama_url))
        logger.info(
            "HISTORY=%d: reuse %s (see benchmark/runs)", history, _rate(answers, reuses_snippet)
        )


if __name__ == "__main__":
    main()
