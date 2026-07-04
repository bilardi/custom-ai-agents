"""Router: selects the message-handling engine from the ENGINE parameter."""

from collections.abc import Iterator, Mapping

from app.engine.base import Engine


class Router:
    """Select an engine by mode and delegate message handling to it."""

    def __init__(self, engines: Mapping[str, Engine], mode: str) -> None:
        """Pick the engine for the mode; fail fast if the mode is not available."""
        if mode not in engines:
            msg = f"unknown ENGINE mode: {mode!r} (available: {sorted(engines)})"
            raise ValueError(msg)
        self._engine = engines[mode]

    def handle(self, message: str) -> Iterator[str] | None:
        """Delegate to the selected engine."""
        return self._engine.handle(message)
