"""Reusable helpers for the benchmark harness: metrics, retrieval and Ollama probing."""

import ast
import re
from pathlib import Path
from typing import Any

import requests

from app.ag.chroma_db import ChromaDb

_FENCE = re.compile(r"```(?:python|py)?\n(.*?)```", re.DOTALL)


def syntax_ok(text: str) -> bool | None:
    """Return whether every Python code block in the text parses.

    Args:
        text: The model answer, possibly containing fenced code blocks.

    Returns:
        True if all blocks parse, False if any fails, None if there is no code.

    """
    blocks = _FENCE.findall(text)
    if not blocks:
        return None
    for block in blocks:
        try:
            ast.parse(block)
        except SyntaxError:
            return False
    return True


def grounded(answer: str) -> bool:
    """Return whether the answer uses the grounded groupby example from the docs."""
    return 'groupby("Origin")' in answer


def generic_from_pandas(answer: str) -> bool:
    """Return whether the answer builds an example DataFrame via dd.from_pandas.

    dd.from_pandas is a real Dask API; using it to fabricate an example instead
    of grounding on the retrieved one marks a generic, ungrounded answer.
    """
    return "from_pandas" in answer


def over_engineered(answer: str) -> bool:
    """Return whether the answer reaches for the delayed API for a simple groupby."""
    return "dask.delayed" in answer or "@delayed" in answer or "delayed(" in answer


def first_keyword_rank(documents: list[str], keyword: str) -> int | None:
    """Return the 0-based rank of the first document containing the keyword.

    Args:
        documents: Ranked retrieval results, most relevant first.
        keyword: The term to look for (case-insensitive).

    Returns:
        The rank of the first matching document, or None if none match.

    """
    lowered = keyword.lower()
    for rank, document in enumerate(documents):
        if lowered in document.lower():
            return rank
    return None


def top_documents(db: ChromaDb, topic: str, query: str, n: int) -> list[str]:
    """Return the top-n indexed documents for a query in a topic, most relevant first."""
    embedding = db.get_embedding(query)
    result = db.client.get_collection(topic).query(
        query_embeddings=[embedding],
        n_results=n,
        include=["documents"],
    )
    documents = result["documents"]
    return list(documents[0]) if documents else []


def installed_models(ollama_url: str, session: Any = requests) -> set[str]:  # noqa: ANN401 (injected HTTP client to Ollama)
    """Return the model names installed on Ollama, both tagged and bare (name before ':')."""
    response = session.get(f"{ollama_url}/api/tags", timeout=10)
    response.raise_for_status()
    names: set[str] = set()
    for model in response.json().get("models", []):
        name = model.get("name", "")
        names.add(name)
        names.add(name.split(":")[0])
    return names


def ollama_reachable(ollama_url: str, session: Any = requests) -> bool:  # noqa: ANN401 (injected HTTP client to Ollama)
    """Return whether the Ollama server answers on /api/tags."""
    try:
        session.get(f"{ollama_url}/api/tags", timeout=10).raise_for_status()
    except requests.RequestException:
        return False
    return True


def write_report(path: Path, title: str, sections: list[tuple[str, str]]) -> None:
    """Write a markdown report with a title and a list of (heading, body) sections."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", ""]
    for heading, body in sections:
        lines.extend((f"## {heading}", "", body, ""))
    path.write_text("\n".join(lines), encoding="utf-8")
