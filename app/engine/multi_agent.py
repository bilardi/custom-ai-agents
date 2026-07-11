"""Multi-agent engine: a triage agent hands off to specialists (OpenAI Agents SDK)."""

from collections.abc import AsyncIterator
from typing import Any

from app.engine.base import Engine, render_prompt


class MultiAgentEngine(Engine):
    """Run an OpenAI Agents SDK entry agent that hands off to specialist agents."""

    def __init__(self, entry: Any) -> None:  # noqa: ANN401 (SDK Agent, duck-typed)
        """Build the engine with the entry (triage) agent that owns the handoffs."""
        self._entry = entry

    async def handle(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Run the entry agent on the conversation window and stream its final answer."""
        return self._answer(render_prompt(messages))

    async def _answer(self, prompt: str) -> AsyncIterator[str]:
        from agents import Runner  # noqa: PLC0415 (opt-in SDK, imported lazily)

        result = await Runner.run(self._entry, prompt)
        yield str(result.final_output)
