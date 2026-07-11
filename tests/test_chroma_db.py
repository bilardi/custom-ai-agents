"""Test the ChromaDb augmented-generation backend."""

from unittest.mock import MagicMock

from app.ag.base import Retriever
from app.ag.chroma_db import ChromaDb


class FakeCollection:
    """In-memory stand-in for a chromadb collection."""

    def __init__(self, name: str, count: int = 0, documents: list[str] | None = None) -> None:
        self.name = name
        self._count = count
        self._documents = documents or []
        self.added: list[dict] = []

    def count(self) -> int:
        return self._count

    def add(self, ids, embeddings, documents, metadatas) -> None:
        self.added.append(
            {"ids": ids, "embeddings": embeddings, "documents": documents, "metadatas": metadatas},
        )
        self._count += len(ids)

    def query(self, query_embeddings, n_results, include) -> dict:
        return {"documents": [self._documents[:n_results]]}


class FakeClient:
    """In-memory stand-in for a chromadb client."""

    def __init__(self, collections: dict[str, FakeCollection] | None = None) -> None:
        self._collections = collections or {}

    def list_collections(self) -> list[FakeCollection]:
        return list(self._collections.values())

    def get_collection(self, name: str) -> FakeCollection:
        return self._collections[name]

    def get_or_create_collection(self, name: str) -> FakeCollection:
        if name not in self._collections:
            self._collections[name] = FakeCollection(name)
        return self._collections[name]

    def delete_collection(self, name: str) -> None:
        self._collections.pop(name, None)


def _session_returning(embedding: list[float]) -> MagicMock:
    session = MagicMock()
    response = MagicMock()
    response.json.return_value = {"embedding": embedding}
    session.post.return_value = response
    return session


def test_chroma_db_is_a_retriever():
    """ChromaDb implements the Retriever interface."""
    assert isinstance(ChromaDb(client=FakeClient()), Retriever)


def test_chunk_text_splits_by_max_words():
    """Text is split into chunks of at most max_words words."""
    db = ChromaDb(client=FakeClient(), max_words=2)
    assert db.chunk_text("a b c d e") == ["a b", "c d", "e"]


def test_reset_collection_deletes_existing_topic():
    """reset_collection removes the topic so it can be rebuilt from scratch."""
    client = FakeClient({"dask": FakeCollection("dask", count=3)})
    db = ChromaDb(client=client)
    db.reset_collection("dask")
    assert db.list_topics() == []


def test_reset_collection_is_noop_when_topic_absent():
    """reset_collection does nothing if the topic does not exist."""
    db = ChromaDb(client=FakeClient())
    db.reset_collection("dask")


def test_chunk_text_overlaps_consecutive_chunks():
    """With overlap, consecutive chunks share overlap words (stride = max_words - overlap)."""
    db = ChromaDb(client=FakeClient(), max_words=3, overlap=1)
    assert db.chunk_text("a b c d e") == ["a b c", "c d e"]


def test_chunk_text_overlap_keeps_a_split_phrase_in_a_middle_chunk():
    """A phrase split across a boundary appears whole in an overlapping middle chunk."""
    db = ChromaDb(client=FakeClient(), max_words=4, overlap=2)
    chunks = db.chunk_text("one two three four five six")
    assert any("three four five" in c for c in chunks)


def test_get_embedding_calls_ollama_and_returns_vector():
    """get_embedding posts the text to Ollama and returns the embedding."""
    session = _session_returning([0.1, 0.2, 0.3])
    db = ChromaDb(
        client=FakeClient(),
        session=session,
        embed_model="qwen3",
        ollama_url="http://x/api/embeddings",
    )
    assert db.get_embedding("hello") == [0.1, 0.2, 0.3]
    session.post.assert_called_once_with(
        "http://x/api/embeddings",
        json={"model": "qwen3", "prompt": "hello"},
    )


def test_list_topics_returns_only_collections_with_documents():
    """Only collections that hold documents are listed as topics."""
    client = FakeClient(
        {
            "dask": FakeCollection("dask", count=5),
            "empty": FakeCollection("empty", count=0),
        },
    )
    db = ChromaDb(client=client)
    assert db.list_topics() == ["dask"]


def test_retrieve_returns_chunks_for_topic():
    """retrieve embeds the query and returns the matching chunks."""
    collection = FakeCollection("dask", count=2, documents=["chunk one", "chunk two"])
    client = FakeClient({"dask": collection})
    session = _session_returning([0.1, 0.2])
    db = ChromaDb(client=client, session=session, top_k=2)
    assert db.retrieve("dask", "how to parallelize") == ["chunk one", "chunk two"]


def test_list_topics_tolerates_extra_kwargs():
    """A spurious kwarg injected by a tool-tuned model is ignored, not raised."""
    client = FakeClient({"dask": FakeCollection("dask", count=5)})
    db = ChromaDb(client=client)
    assert db.list_topics(toolbench_rapidapi_key="x") == ["dask"]


def test_retrieve_tolerates_extra_kwargs():
    """A spurious kwarg injected by a tool-tuned model is ignored, not raised."""
    collection = FakeCollection("dask", count=2, documents=["chunk one", "chunk two"])
    client = FakeClient({"dask": collection})
    db = ChromaDb(client=client, session=_session_returning([0.1, 0.2]), top_k=2)
    assert db.retrieve("dask", "q", toolbench_rapidapi_key="x") == ["chunk one", "chunk two"]


def test_retrieve_unknown_topic_degrades_with_available_topics():
    """retrieve on a topic with no documents returns a hint, not an exception."""
    client = FakeClient({"dask": FakeCollection("dask", count=2, documents=["c"])})
    db = ChromaDb(client=client, session=_session_returning([0.1]))
    result = db.retrieve("dask.dataframe", "groupby")
    assert len(result) == 1
    assert "dask.dataframe" in result[0]
    assert "Available topics" in result[0]


def test_add_indexes_each_chunk():
    """add splits the text and stores one entry per chunk."""
    client = FakeClient()
    session = _session_returning([0.0])
    db = ChromaDb(client=client, session=session, max_words=2)
    added = db.add("dask", "doc.txt", "a b c d")
    assert added == 2
    collection = client.get_collection("dask")
    assert collection.added[0]["ids"] == ["doc.txt-0"]
    assert collection.added[1]["ids"] == ["doc.txt-1"]


def test_extract_text_from_html_drops_scripts(tmp_path):
    """HTML extraction returns visible text without script content."""
    html = "<html><head><script>bad()</script></head><body><p>Hello world</p></body></html>"
    path = tmp_path / "doc.html"
    path.write_text(html, encoding="utf-8")
    db = ChromaDb(client=FakeClient())
    text = db.extract_text_from_html(str(path))
    assert "Hello world" in text
    assert "bad()" not in text


def test_index_folder_indexes_html_documents(tmp_path):
    """index_folder reads supported files and indexes their chunks."""
    (tmp_path / "doc.html").write_text("<body><p>alpha beta gamma</p></body>", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")
    client = FakeClient()
    session = _session_returning([0.0])
    db = ChromaDb(client=client, session=session, max_words=100)
    chunks = db.index_folder(str(tmp_path), "dask")
    assert chunks == 1
    assert client.get_collection("dask").count() == 1
