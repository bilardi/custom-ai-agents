"""Per-request progress trace shared between the engine and the sub-agents.

The engine starts a queue for the current request; the tool-trace callback and the
sub-agents (coder, reviewer) push progress lines to it via ``emit``. When no queue
is active (tracing off), ``emit`` is a no-op.
"""

import asyncio
import contextvars

_queue: contextvars.ContextVar[asyncio.Queue[str] | None] = contextvars.ContextVar(
    "progress_trace_queue", default=None
)


def start_trace() -> asyncio.Queue[str]:
    """Create a fresh trace queue for the current context and return it."""
    queue: asyncio.Queue[str] = asyncio.Queue()
    _queue.set(queue)
    return queue


def emit(line: str) -> None:
    """Push a progress line to the current trace queue, if tracing is on."""
    queue = _queue.get()
    if queue is not None:
        queue.put_nowait(line)
