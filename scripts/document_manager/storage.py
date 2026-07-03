"""Index a folder of documents into a ChromaDB topic.

Run from the repo root:
    DOCS_FOLDER=data/documents/dask COLLECTION=dask \
        uv run python -m scripts.document_manager.storage
"""

import logging
import os
import time

from app.ag.chroma_db import ChromaDb

logger = logging.getLogger("storage")


def main() -> None:
    """Index DOCS_FOLDER into COLLECTION using Ollama embeddings."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", force=True)
    collection = os.environ.get("COLLECTION", "dask")
    docs_folder = os.environ.get("DOCS_FOLDER", "data/documents/dask")
    embed_model = os.environ.get("EMBED_MODEL", "qwen3")
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    max_words = int(os.environ.get("MAX_WORDS", "300"))

    start = time.time()
    db = ChromaDb(
        embed_model=embed_model,
        ollama_url=f"{ollama_url}/api/embeddings",
        max_words=max_words,
    )
    chunks = db.index_folder(docs_folder, collection)
    logger.info("indexed %s chunks into %s in %.1fs", chunks, collection, time.time() - start)


if __name__ == "__main__":
    main()
