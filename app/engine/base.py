"""Common interface for message-handling engines."""

from abc import ABC, abstractmethod
from collections.abc import Iterator


class Engine(ABC):
    """Strategy that turns an incoming message into a token stream or a pass-through."""

    @abstractmethod
    async def handle(self, message: str) -> Iterator[str] | None:
        """Return the answer as a token stream, or None to pass through to Ollama."""
