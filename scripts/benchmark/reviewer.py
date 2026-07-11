"""Benchmark the reviewer sub-agent: catch rate vs false-positive rate on a labeled set.

Runs the Reviewer over a fixed labeled set of code samples N times and reports, per
case, how often it flags the code. Gives the catch rate (the invented-API case), the
false-positive rate (correct cases) and, separately, the flag rate on a correct-but-
generic answer (a grounding-strictness call, reported for discussion, not scored).
Writes benchmark/runs/reviewer-<model>.md. Run from the repo root:

    REVIEWER_MODEL=llama3.2:3b BENCH_RUNS=10 OLLAMA_URL=http://127.0.0.1:11435 \
        uv run python -m scripts.benchmark.reviewer
"""

import asyncio
import logging
import os
from collections.abc import Awaitable, Callable
from pathlib import Path

from any_agent import AgentConfig, AnyAgent

from app.agents.reviewer import Reviewer
from app.prompts import load_prompt
from scripts.benchmark.helpers import write_report

logger = logging.getLogger("benchmark.reviewer")

RUNS_DIR = Path("benchmark/runs")

TASK = "Write Dask code to parallelize a groupby aggregation on a DataFrame."

CONTEXT = """Dask DataFrame parallelizes pandas. To aggregate by group, call groupby on a
Dask DataFrame and then .compute() to run it. Tutorial example on the flights dataset:

    import dask.dataframe as dd
    ddf = dd.read_csv("nycflights/*.csv")
    result = ddf.groupby("Origin").DepDelay.mean().compute()

dd.from_pandas(df, npartitions=...) converts a pandas DataFrame into a Dask DataFrame."""

# label: "flag" = the reviewer should report a problem; "ok" = it should return OK;
# "generic" = correct but ignores the retrieved example (a grounding-strictness call,
# reported separately, not scored as pass/fail).
CASES: list[dict[str, str]] = [
    {
        "name": "invented-api",
        "label": "flag",
        "code": (
            "import dask.dataframe as dd\n\n"
            "@dd(delayed=True)\n"
            "def mean_delay(ddf):\n"
            '    return ddf.groupby("Origin").DepDelay.mean()\n\n'
            'result = mean_delay(dd.read_csv("nycflights/*.csv")).compute()'
        ),
    },
    {
        "name": "good-grounded",
        "label": "ok",
        "code": (
            "import dask.dataframe as dd\n\n"
            'ddf = dd.read_csv("nycflights/*.csv")\n'
            'result = ddf.groupby("Origin").DepDelay.mean().compute()\n'
            "print(result)"
        ),
    },
    {
        "name": "valid-variation",
        "label": "ok",
        "code": (
            "import dask.dataframe as dd\n\n"
            'ddf = dd.read_csv("nycflights/*.csv")\n'
            'result = ddf.groupby("Origin").agg({"DepDelay": "mean"}).compute()\n'
            "print(result)"
        ),
    },
    {
        "name": "generic-ungrounded",
        "label": "generic",
        "code": (
            "import dask.dataframe as dd\n"
            "import pandas as pd\n\n"
            'pdf = pd.DataFrame({"Origin": ["JFK", "LAX", "JFK"], "DepDelay": [10, 5, 20]})\n'
            "ddf = dd.from_pandas(pdf, npartitions=2)\n"
            'result = ddf.groupby("Origin").DepDelay.mean().compute()\n'
            "print(result)"
        ),
    },
]


def _make_factory(model: str, ollama_url: str) -> Callable[[], Awaitable[AnyAgent]]:
    async def factory() -> AnyAgent:
        return await AnyAgent.create_async(
            "tinyagent",
            AgentConfig(
                model_id=f"openai:{model}",
                api_base=f"{ollama_url}/v1",
                api_key="ollama",
                instructions=load_prompt("reviewer"),
            ),
        )

    return factory


async def run(model: str, runs: int, ollama_url: str) -> dict[str, list[bool]]:
    """Run the reviewer `runs` times per case; write and return {case name: [flagged...]}."""
    reviewer = Reviewer(agent_factory=_make_factory(model, ollama_url))
    flags: dict[str, list[bool]] = {}
    for case in CASES:
        case_flags: list[bool] = []
        for _ in range(runs):
            verdict = await reviewer.review(TASK, case["code"], CONTEXT)
            case_flags.append(bool(verdict))
        flags[case["name"]] = case_flags
    _report(model, flags)
    return flags


def _pooled_rate(labels: set[str], flags: dict[str, list[bool]], by_label: dict[str, str]) -> float:
    picked = [f for name, f in flags.items() if by_label[name] in labels]
    total = sum(len(f) for f in picked)
    return sum(sum(f) for f in picked) / total if total else 0.0


def _report(model: str, flags: dict[str, list[bool]]) -> Path:
    by_label = {case["name"]: case["label"] for case in CASES}
    rows = "\n".join(
        f"| {name} | {by_label[name]} | {sum(f)}/{len(f)} |" for name, f in flags.items()
    )
    catch = _pooled_rate({"flag"}, flags, by_label)
    false_positive = _pooled_rate({"ok"}, flags, by_label)
    generic = _pooled_rate({"generic"}, flags, by_label)
    summary = (
        f"task: `{TASK}`\n\n"
        f"catch rate (invented-api, higher better) {catch:.0%}; "
        f"false-positive rate (correct cases, lower better) {false_positive:.0%}; "
        f"generic-answer flag rate (grounding call, for discussion) {generic:.0%}"
    )
    table = f"| case | expected | flagged |\n|---|---|---|\n{rows}"
    path = RUNS_DIR / f"reviewer-{model.replace(':', '_')}.md"
    write_report(path, f"reviewer - {model}", [("summary", summary), ("per case", table)])
    return path


def main() -> None:
    """Run the reviewer benchmark for REVIEWER_MODEL over BENCH_RUNS runs and log the rates."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", force=True)
    model = os.getenv("REVIEWER_MODEL", "llama3.2:3b")
    runs = int(os.getenv("BENCH_RUNS", "10"))
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    flags = asyncio.run(run(model, runs, ollama_url))
    logger.info(
        "%s: %s (see benchmark/runs)",
        model,
        {name: f"{sum(f)}/{len(f)}" for name, f in flags.items()},
    )


if __name__ == "__main__":
    main()
