"""Common interface for message-handling engines."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator


class Engine(ABC):
    """Strategy that turns an incoming message into a token stream or a pass-through."""

    @abstractmethod
    async def handle(
        self, messages: list[dict[str, str]]
    ) -> AsyncIterator[str] | Iterator[str] | None:
        """Handle the conversation window and return a token stream, or None to pass through.

        Args:
            messages: The trailing conversation window (Ollama `{role, content}` items),
                sized by the HISTORY parameter; the last item is the current message.

        """
