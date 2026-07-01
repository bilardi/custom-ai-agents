"""Test the Router engine selection."""

from unittest.mock import MagicMock

import pytest

from app.router import Router


def test_router_delegates_to_selected_engine():
    engine = MagicMock()
    engine.handle.return_value = "RESULT"
    router = Router(engines={"deterministic": engine}, mode="deterministic")
    assert router.handle("hi") == "RESULT"
    engine.handle.assert_called_once_with("hi")


def test_router_raises_on_unknown_mode():
    engine = MagicMock()
    with pytest.raises(ValueError, match="tool-agent"):
        Router(engines={"deterministic": engine}, mode="tool-agent")
