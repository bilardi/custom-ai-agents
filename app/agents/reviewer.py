"""Reviewer: a sub-agent that critiques code for correctness and grounding."""

from collections.abc import Awaitable, Callable
from typing import Any


class Reviewer:
    """A specialist sub-agent that reviews code and reports concrete problems."""

    def __init__(self, agent_factory: Callable[[], Awaitable[Any]]) -> None:
        """Build the reviewer with an async factory that creates its sub-agent."""
        self._agent_factory = agent_factory
        self._agent: Any = None

    async def review(self, task: str, code: str, context: str = "") -> str:
        """Review the code against the task and documentation.

        Returns the concrete problems found (wrong or invented APIs, logic errors,
        claims not supported by the context), or an empty string if the code is
        correct and grounded.
        """
        if self._agent is None:
            self._agent = await self._agent_factory()
        prompt = f"Task: {task}\n\nCode to review:\n{code}"
        if context:
            prompt += f"\n\nDocumentation context:\n{context}"
        trace = await self._agent.run_async(prompt)
        verdict = str(trace.final_output).strip()
        return "" if verdict.upper() == "OK" else verdict
