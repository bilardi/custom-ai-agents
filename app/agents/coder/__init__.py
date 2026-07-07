"""Coder: a code-writing sub-agent exposed to the orchestrator as a tool."""

from collections.abc import Awaitable, Callable
from typing import Any

from app.agents.coder.code_validator import check_code, extract_code_blocks
from app.trace import emit


class Coder:
    """A specialist sub-agent that writes code, checked before it is returned."""

    def __init__(
        self,
        agent_factory: Callable[[], Awaitable[Any]],
        reviewer: Any = None,  # noqa: ANN401 (optional Reviewer collaborator, duck-typed)
    ) -> None:
        """Build the coder with an async factory and an optional code reviewer."""
        self._agent_factory = agent_factory
        self._agent: Any = None
        self._reviewer = reviewer

    async def write_code(self, task: str, context: str = "", **_kwargs: Any) -> str:  # noqa: ANN401
        """Write Python code for a coding task, grounded on the given documentation.

        Delegate here whenever the user asks to write, generate or fix code. Pass the
        coding task and, as context, the relevant documentation already retrieved, so
        the code stays anchored to it. Returns the code with a short explanation.

        Args:
            task: The coding task to solve.
            context: Documentation chunks to ground the code on.

        Returns:
            The code answer (Markdown with fenced Python), checked once.
        """
        # Some ToolBench-tuned models inject spurious args (e.g. toolbench_rapidapi_key);
        # tinyagent excludes **kwargs from the tool schema, so they are just absorbed here.
        if self._agent is None:
            self._agent = await self._agent_factory()
        answer = await self._run(task, context)
        problems = self._check(answer)
        if self._reviewer is not None:
            emit("> reviewing code...\n\n")
            critique = await self._reviewer.review(task, answer, context)
            if critique:
                problems = f"{problems}\n{critique}".strip() if problems else critique
        if problems:
            emit("> revising code...\n\n")
            answer = await self._run(task, context, previous=answer, feedback=problems)
        return answer

    async def _run(self, task: str, context: str, previous: str = "", feedback: str = "") -> str:
        prompt = f"Task: {task}"
        if context:
            prompt += f"\n\nDocumentation context:\n{context}"
        if feedback:
            prompt += (
                f"\n\nYour previous answer:\n{previous}"
                f"\n\nIt had these problems, fix them and return corrected code:\n{feedback}"
            )
        trace = await self._agent.run_async(prompt)
        return str(trace.final_output)

    @staticmethod
    def _check(answer: str) -> str:
        problems: list[str] = []
        for block in extract_code_blocks(answer):
            report = check_code(block)
            if not report.valid:
                problems.append(f"{report.kind}: {'; '.join(report.issues)}")
        return "\n".join(problems)
