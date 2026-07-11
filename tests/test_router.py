"""Test the Router engine selection."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.router import Router


async def test_router_delegates_to_selected_engine():
    engine = MagicMock()
    engine.handle = AsyncMock(return_value="RESULT")
    router = Router(engines={"deterministic": engine}, mode="deterministic")
    messages = [{"role": "user", "content": "hi"}]
    assert await router.handle(messages) == "RESULT"
    engine.handle.assert_awaited_once_with(messages)


def test_router_raises_on_unknown_mode():
    engine = MagicMock()
    with pytest.raises(ValueError, match="tool-agent"):
        Router(engines={"deterministic": engine}, mode="tool-agent")
