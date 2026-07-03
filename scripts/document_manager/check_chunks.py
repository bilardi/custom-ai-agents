"""Show the indexed topics.

Run from the repo root:
    uv run python -m scripts.document_manager.check_chunks
"""

import logging
import os

from app.ag.chroma_db import ChromaDb

logger = logging.getLogger("check_chunks")


def main() -> None:
    """List the topics that hold documents."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", force=True)
    embed_model = os.environ.get("EMBED_MODEL", "qwen3")
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    db = ChromaDb(embed_model=embed_model, ollama_url=f"{ollama_url}/api/embeddings")
    logger.info("indexed topics: %s", db.list_topics())


if __name__ == "__main__":
    main()
