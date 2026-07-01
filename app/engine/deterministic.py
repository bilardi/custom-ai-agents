"""Deterministic engine: fixed rules, no LLM decides which action to take."""

import re
from collections.abc import Callable

from app.ag.base import Retriever
from app.engine.base import Engine
from app.tools.web_browsing import WebBrowser

_TAG = re.compile(r"(?:^|\s)/([A-Za-z0-9_]+)")
_URL = re.compile(r"https?://\S+")


def _extract_tag(text: str) -> str | None:
    match = _TAG.search(text)
    return match.group(1) if match else None


def _extract_url(text: str) -> str | None:
    match = _URL.search(text)
    return match.group(0) if match else None


def _prompt(context: str, question: str) -> str:
    return (
        "Use only the following information to answer the question:\n"
        f"{context}\n"
        f"Question: {question}"
    )


class DeterministicEngine(Engine):
    """Fixed rules: /tag -> RAG, /web -> search, url -> visit, else pass-through."""

    def __init__(self, ag: Retriever, web: WebBrowser, generate: Callable[[str], str]) -> None:
        """Build the engine with injected knowledge, web and model-call collaborators."""
        self._ag = ag
        self._web = web
        self._generate = generate

    def handle(self, message: str) -> str | None:
        """Apply the deterministic rules and return the answer, or None to pass through."""
        tag = _extract_tag(message)
        if tag == "web":
            query = self._strip_tag(message, tag)
            return self._generate(_prompt(self._web.search_web(query), query))
        if tag and tag in self._ag.list_topics():
            query = self._strip_tag(message, tag)
            context = "\n".join(self._ag.retrieve(tag, query))
            return self._generate(_prompt(context, query))
        url = _extract_url(message)
        if url:
            return self._generate(_prompt(self._web.visit_webpage(url), message))
        return None

    @staticmethod
    def _strip_tag(message: str, tag: str) -> str:
        return message.replace(f"/{tag}", "", 1).strip()
