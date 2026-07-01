"""Common interface for message-handling engines."""

from abc import ABC, abstractmethod


class Engine(ABC):
    """Strategy that turns an incoming message into an answer or a pass-through."""

    @abstractmethod
    def handle(self, message: str) -> str | None:
        """Return the answer, or None to pass the message through to Ollama."""
