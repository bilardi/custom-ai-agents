"""Common interface for message-handling engines."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator


class Engine(ABC):
    """Strategy that turns an incoming message into a token stream or a pass-through."""

    @abstractmethod
    async def handle(self, message: str) -> AsyncIterator[str] | Iterator[str] | None:
        """Return the answer as a (sync or async) token stream, or None to pass through."""
