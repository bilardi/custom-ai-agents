"""Common interface for message-handling engines."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator


def render_prompt(messages: list[dict[str, str]]) -> str:
    """Render a conversation window as a single prompt for an agent.

    A single message is returned unchanged (default HISTORY=1); multiple messages
    are rendered as a `role: content` transcript so the agent sees the prior turns.
    """
    if len(messages) == 1:
        return messages[0]["content"]
    return "\n".join(f"{message['role']}: {message['content']}" for message in messages)


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
