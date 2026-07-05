"""Tool-agent engine: an any_agent orchestrator decides which tools to use."""

import asyncio
import contextvars
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from any_agent.callbacks.base import Callback
from any_agent.callbacks.context import Context

from app.engine.base import Engine

# Per-request queue the trace callback writes to; None when tracing is off.
_trace_queue: contextvars.ContextVar[asyncio.Queue[str] | None] = contextvars.ContextVar(
    "tool_trace_queue", default=None
)


def _describe_tool(name: str, args: dict[str, Any]) -> str:
    """Return a human-readable progress line for a tool about to run.

    Each line is a self-contained markdown blockquote paragraph (trailing blank
    line), so lines render one per row and the final answer stays separate.
    """
    if name == "list_topics":
        return "> checking indexed topics...\n\n"
    if name == "retrieve":
        return f"> reading local docs on '{args.get('topic', '')}'...\n\n"
    if name == "search_web":
        return f"> searching the web for '{args.get('query', '')}'...\n\n"
    if name == "visit_webpage":
        return f"> opening {args.get('url', '')}...\n\n"
    return f"> running {name}...\n\n"


class ToolTraceCallback(Callback):
    """Stream a progress line to the current request queue before each tool call."""

    def before_tool_execution(
        self,
        context: Context,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401, ARG002
    ) -> Context:
        """Push a progress line for the tool about to run, if tracing is on."""
        queue = _trace_queue.get()
        if queue is not None and args:
            request = args[0]
            queue.put_nowait(_describe_tool(request.get("name", ""), request.get("arguments", {})))
        return context


class ToolAgentEngine(Engine):
    """Delegate the message to an any_agent orchestrator that chooses the tools."""

    def __init__(
        self,
        agent_factory: Callable[[], Awaitable[Any]],
        *,
        show_trace: bool = False,
    ) -> None:
        """Build the engine with an async factory that creates the orchestrator.

        The agent is created lazily on first use via the async API, because
        any_agent's sync API cannot run inside a running asyncio loop. When
        show_trace is on, a progress line per tool call is streamed before the
        final answer.
        """
        self._agent_factory = agent_factory
        self._agent: Any = None
        self._show_trace = show_trace

    async def handle(self, message: str) -> AsyncIterator[str]:
        """Run the agent and stream its answer (optionally preceded by a tool trace)."""
        if self._agent is None:
            self._agent = await self._agent_factory()
        if self._show_trace:
            return self._answer_with_trace(message)
        return self._answer(message)

    async def _answer(self, message: str) -> AsyncIterator[str]:
        trace = await self._agent.run_async(message)
        yield str(trace.final_output)

    async def _answer_with_trace(self, message: str) -> AsyncIterator[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        _trace_queue.set(queue)
        task = asyncio.ensure_future(self._agent.run_async(message))
        while not task.done() or not queue.empty():
            getter = asyncio.ensure_future(queue.get())
            done, _ = await asyncio.wait({getter, task}, return_when=asyncio.FIRST_COMPLETED)
            if getter in done:
                yield getter.result()
            else:
                getter.cancel()
        trace = task.result()
        yield str(trace.final_output)
