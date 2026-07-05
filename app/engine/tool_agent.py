"""Tool-agent engine: an any_agent orchestrator decides which tools to use."""

from collections.abc import Awaitable, Callable, Iterator
from typing import Any

from app.engine.base import Engine


class ToolAgentEngine(Engine):
    """Delegate the message to an any_agent orchestrator that chooses the tools."""

    def __init__(self, agent_factory: Callable[[], Awaitable[Any]]) -> None:
        """Build the engine with an async factory that creates the orchestrator.

        The agent is created lazily on first use via the async API, because
        any_agent's sync API cannot run inside a running asyncio loop.
        """
        self._agent_factory = agent_factory
        self._agent: Any = None

    async def handle(self, message: str) -> Iterator[str] | None:
        """Run the agent and return its final answer as a single-chunk stream."""
        if self._agent is None:
            self._agent = await self._agent_factory()
        trace = await self._agent.run_async(message)
        return iter([str(trace.final_output)])
