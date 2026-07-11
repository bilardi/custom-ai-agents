"""Router: selects the message-handling engine from the ENGINE parameter."""

from collections.abc import AsyncIterator, Iterator, Mapping

from app.engine.base import Engine


class Router:
    """Select an engine by mode and delegate message handling to it."""

    def __init__(self, engines: Mapping[str, Engine], mode: str) -> None:
        """Pick the engine for the mode; fail fast if the mode is not available."""
        if mode not in engines:
            msg = f"unknown ENGINE mode: {mode!r} (available: {sorted(engines)})"
            raise ValueError(msg)
        self._engine = engines[mode]

    async def handle(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str] | Iterator[str] | None:
        """Delegate the conversation window to the selected engine."""
        return await self._engine.handle(messages)
