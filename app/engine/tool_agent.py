"""Tool-agent engine: an any_agent orchestrator decides which tools to use."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from any_agent.callbacks.base import Callback
from any_agent.callbacks.context import Context

from app.engine.base import Engine
from app.trace import emit, start_trace

# Signatures of a tool call leaked into the final answer as text (seen with some
# local models even via /v1): a malformed reply that should be regenerated once.
_MALFORMED = ("<|python_tag|>", '{"name":', '"parameters"', "write_code(")


def _is_malformed(text: str) -> bool:
    """Return True if the final answer leaked a tool call as text instead of a real reply."""
    return any(marker in text for marker in _MALFORMED)


def _to_prompt(messages: list[dict[str, str]]) -> str:
    """Render the conversation window as the agent prompt.

    A single message is passed through unchanged (default HISTORY=1); multiple
    messages are rendered as a `role: content` transcript so the agent sees the
    prior turns.
    """
    if len(messages) == 1:
        return messages[0]["content"]
    return "\n".join(f"{message['role']}: {message['content']}" for message in messages)


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
    if name == "write_code":
        return "> writing code...\n\n"
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
        if args:
            request = args[0]
            emit(_describe_tool(request.get("name", ""), request.get("arguments", {})))
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

    async def handle(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        """Run the agent on the conversation window and stream its answer.

        The window (sized by HISTORY) is rendered into the prompt, optionally
        preceded by a tool trace.
        """
        if self._agent is None:
            self._agent = await self._agent_factory()
        prompt = _to_prompt(messages)
        if self._show_trace:
            return self._answer_with_trace(prompt)
        return self._answer(prompt)

    async def _final(self, message: str) -> str:
        """Run the agent and return its final answer, regenerating once if malformed."""
        trace = await self._agent.run_async(message)
        answer = str(trace.final_output)
        if _is_malformed(answer):
            trace = await self._agent.run_async(message)
            answer = str(trace.final_output)
        return answer

    async def _answer(self, message: str) -> AsyncIterator[str]:
        yield await self._final(message)

    async def _answer_with_trace(self, message: str) -> AsyncIterator[str]:
        queue = start_trace()
        task = asyncio.ensure_future(self._final(message))
        while not task.done() or not queue.empty():
            getter = asyncio.ensure_future(queue.get())
            done, _ = await asyncio.wait({getter, task}, return_when=asyncio.FIRST_COMPLETED)
            if getter in done:
                yield getter.result()
            else:
                getter.cancel()
        yield task.result()
