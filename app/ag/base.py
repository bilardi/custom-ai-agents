"""Common interface for augmented-generation backends."""

from abc import ABC, abstractmethod


class Retriever(ABC):
    """Read side of a local knowledge source.

    Provisional interface, currently designed on a single backend: it may change
    when a second backend (e.g. a graph store) is added.
    """

    @abstractmethod
    def list_topics(self) -> list[str]:
        """Return the topics that hold documents."""

    @abstractmethod
    def retrieve(self, topic: str, query: str) -> list[str]:
        """Return the chunks relevant to the query within the topic."""
