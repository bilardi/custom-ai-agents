"""Benchmark multi-agent handoff routing: whether the triage reaches the right specialist.

Two requests (a Python one, an AWS one) run N times; measures whether the entry
(triage) agent hands off to the expected specialist (RunResult.last_agent) and
whether the run completes. Compare a small vs a capable local model. Writes
benchmark/runs/multi_agent-<model>.md. Run from the repo root:

    MODEL=llama3.2:3b BENCH_RUNS=5 OLLAMA_URL=http://127.0.0.1:11435 \
        uv run python -m scripts.benchmark.multi_agent
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from app.prompts import load_prompt
from scripts.benchmark.helpers import write_report

logger = logging.getLogger("benchmark.multi_agent")

RUNS_DIR = Path("benchmark/runs")

CASES: list[dict[str, str]] = [
    {
        "name": "python",
        "expert": "python_expert",
        "prompt": "Write a Python function to reverse a string.",
    },
    {
        "name": "aws",
        "expert": "aws_expert",
        "prompt": "How do I create an S3 bucket with the AWS CLI?",
    },
]

# (routed_agent_name, routed_correctly); routed_agent_name is "" if the run errored.
Outcome = tuple[str, bool]


def _entry(model: str, ollama_url: str) -> Any:  # noqa: ANN401 (SDK Agent, duck-typed)
    from agents import (  # noqa: PLC0415 (opt-in SDK)
        Agent,
        OpenAIChatCompletionsModel,
        set_tracing_disabled,
    )
    from openai import AsyncOpenAI  # noqa: PLC0415 (opt-in SDK)

    set_tracing_disabled(True)
    sdk_model = OpenAIChatCompletionsModel(
        model=model,
        openai_client=AsyncOpenAI(base_url=f"{ollama_url}/v1", api_key="ollama"),
    )
    python_expert = Agent(
        name="python_expert",
        handoff_description="Writing or fixing Python code",
        instructions=load_prompt("python_expert"),
        model=sdk_model,
    )
    aws_expert = Agent(
        name="aws_expert",
        handoff_description="AWS services, CLI and infrastructure",
        instructions=load_prompt("aws_expert"),
        model=sdk_model,
    )
    return Agent(
        name="triage",
        instructions=load_prompt("triage"),
        model=sdk_model,
        handoffs=[python_expert, aws_expert],
    )


async def run(model: str, runs: int, ollama_url: str) -> dict[str, list[Outcome]]:
    """Run each case `runs` times for `model`; write and return {case: [(routed, correct)]}."""
    from agents import Runner  # noqa: PLC0415 (opt-in SDK)

    entry = _entry(model, ollama_url)
    results: dict[str, list[Outcome]] = {}
    for case in CASES:
        outcomes: list[Outcome] = []
        for _ in range(runs):
            result = await Runner.run(entry, case["prompt"], max_turns=6)
            routed = getattr(result.last_agent, "name", "")
            outcomes.append((routed, routed == case["expert"]))
        results[case["name"]] = outcomes
    _report(model, results)
    return results


def _report(model: str, results: dict[str, list[Outcome]]) -> Path:
    """Write per-run routing and the accuracy to benchmark/runs, returning the path."""
    by_expert = {case["name"]: case["expert"] for case in CASES}
    lines: list[str] = []
    correct = total = 0
    for name, outcomes in results.items():
        hits = sum(1 for _, ok in outcomes if ok)
        correct += hits
        total += len(outcomes)
        routed = ", ".join(agent or "error" for agent, _ in outcomes)
        lines.append(f"| {name} | {by_expert[name]} | {hits}/{len(outcomes)} | {routed} |")
    accuracy = correct / total if total else 0.0
    summary = f"routing accuracy (right specialist) {accuracy:.0%} ({correct}/{total})"
    table = "| case | expected | correct | routed to |\n|---|---|---|---|\n" + "\n".join(lines)
    path = RUNS_DIR / f"multi_agent-{model.replace(':', '_')}.md"
    write_report(path, f"multi-agent - {model}", [("summary", summary), ("per case", table)])
    return path


def main() -> None:
    """Run the multi-agent routing benchmark for MODEL over BENCH_RUNS runs and log accuracy."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", force=True)
    model = os.getenv("MODEL", "llama3.2:3b")
    runs = int(os.getenv("BENCH_RUNS", "5"))
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    results = asyncio.run(run(model, runs, ollama_url))
    correct = sum(1 for outcomes in results.values() for _, ok in outcomes if ok)
    total = sum(len(outcomes) for outcomes in results.values())
    logger.info("%s: routing %d/%d (see benchmark/runs)", model, correct, total)


if __name__ == "__main__":
    main()
