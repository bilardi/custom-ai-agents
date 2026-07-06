"""Coder: a code-writing sub-agent exposed to the orchestrator as a tool."""

from collections.abc import Awaitable, Callable
from typing import Any

from app.agents.coder.code_validator import check_code, extract_code_blocks


class Coder:
    """A specialist sub-agent that writes code, checked before it is returned."""

    def __init__(self, agent_factory: Callable[[], Awaitable[Any]]) -> None:
        """Build the coder with an async factory that creates its sub-agent."""
        self._agent_factory = agent_factory
        self._agent: Any = None

    async def write_code(self, task: str, context: str = "") -> str:
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
        if self._agent is None:
            self._agent = await self._agent_factory()
        answer = await self._run(task, context)
        problems = self._review(answer)
        if problems:
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
    def _review(answer: str) -> str:
        problems: list[str] = []
        for block in extract_code_blocks(answer):
            report = check_code(block)
            if not report.valid:
                problems.append(f"{report.kind}: {'; '.join(report.issues)}")
        return "\n".join(problems)
