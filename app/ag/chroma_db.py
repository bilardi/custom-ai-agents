"""ChromaDB augmented-generation backend: retrieval and local indexing."""

from pathlib import Path
from typing import Any

import chromadb
import pdfplumber
import requests
from bs4 import BeautifulSoup
from chromadb.config import Settings

from app.ag.base import Retriever


class ChromaDb(Retriever):
    """Vector knowledge source backed by ChromaDB, with local indexing.

    The read side (`list_topics`, `retrieve`) is the `Retriever` interface; the
    indexing side (`add`, `index_folder`, extraction helpers) is used by scripts.
    """

    def __init__(  # noqa: PLR0913
        self,
        path: str = "data/chroma_db",
        model: str = "qwen3",
        ollama_url: str = "http://localhost:11434/api/embeddings",
        max_words: int = 300,
        top_k: int = 3,
        client: Any = None,  # noqa: ANN401 (injected chromadb client or a test double)
        session: Any = None,  # noqa: ANN401 (injected HTTP client for embeddings)
    ) -> None:
        """Build the backend with connection defaults and injectable clients."""
        self.model = model
        self.ollama_url = ollama_url
        self.max_words = max_words
        self.top_k = top_k
        self.client = client or chromadb.PersistentClient(
            path=path,
            settings=Settings(anonymized_telemetry=False),
        )
        self.session = session or requests

    def list_topics(self) -> list[str]:
        """Return the names of the collections that hold documents."""
        return [c.name for c in self.client.list_collections() if c.count() > 0]

    def retrieve(self, topic: str, query: str) -> list[str]:
        """Return the top chunks of a topic relevant to the query."""
        collection = self.client.get_collection(topic)
        embedding = self.get_embedding(query)
        result = collection.query(
            query_embeddings=[embedding],
            n_results=self.top_k,
            include=["documents"],
        )
        documents = result["documents"]
        return list(documents[0]) if documents else []

    def get_embedding(self, text: str) -> list[float]:
        """Return the embedding of the text computed by Ollama."""
        response = self.session.post(self.ollama_url, json={"model": self.model, "prompt": text})
        return response.json()["embedding"]

    def chunk_text(self, text: str, max_words: int | None = None) -> list[str]:
        """Split the text into chunks of at most max_words words."""
        max_words = max_words or self.max_words
        words = text.split()
        return [" ".join(words[i : i + max_words]) for i in range(0, len(words), max_words)]

    def add(self, topic: str, filename: str, text: str) -> int:
        """Index the text of a file into a topic and return the chunk count."""
        collection = self.client.get_or_create_collection(topic)
        count = 0
        for i, chunk in enumerate(self.chunk_text(text)):
            collection.add(
                ids=[f"{filename}-{i}"],
                embeddings=[self.get_embedding(chunk)],
                documents=[chunk],
                metadatas=[{"file": filename}],
            )
            count += 1
        return count

    def extract_text_from_html(self, filepath: str) -> str:
        """Extract the visible text from an HTML file."""
        with Path(filepath).open(encoding="utf-8") as f:
            html = f.read()
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "meta", "link", "head", "footer"]):
            tag.extract()
        return soup.get_text(separator=" ", strip=True)

    def extract_text_from_pdf(self, filepath: str, top: int = 50, bottom: int = 750) -> str:
        """Extract the text from a PDF, dropping header/footer by page position."""
        full_text: list[str] = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                lines = [obj["text"] for obj in page.extract_words() if top < obj["top"] < bottom]
                full_text.append(" ".join(lines))
        return " ".join(full_text)

    def index_folder(self, folder: str, topic: str) -> int:
        """Index every supported file of a folder into a topic; return chunk count."""
        chunks = 0
        for path in Path(folder).iterdir():
            if path.suffix == ".html":
                text = self.extract_text_from_html(str(path))
            elif path.suffix == ".pdf":
                text = self.extract_text_from_pdf(str(path))
            else:
                continue
            chunks += self.add(topic, path.name, text)
        return chunks
