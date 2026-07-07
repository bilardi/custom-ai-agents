"""Test the progress trace primitive."""

from app.trace import emit, start_trace


def test_emit_without_queue_is_noop():
    emit("ignored")  # no queue in this context: must not raise


async def test_emit_pushes_to_current_queue():
    queue = start_trace()
    emit("> hello\n\n")
    assert queue.get_nowait() == "> hello\n\n"
