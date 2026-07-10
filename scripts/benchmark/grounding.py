"""Benchmark retrieval rank of the target chunk (reproducible).

Reindexes the dask corpus with the winning configuration (nomic-embed-text,
MAX_WORDS=500, OVERLAP=0) into a throwaway topic, then measures the 0-based rank
of the first chunk containing the target keyword in the top-20 results. The
retrieval is deterministic, so the ranks reproduce exactly. Writes the ranks to
benchmark/runs/grounding-nomic-w500.md. Run from the repo root:

    OLLAMA_URL=http://127.0.0.1:11435 uv run python -m scripts.benchmark.grounding
"""

import logging
import os
from pathlib import Path

from app.ag.chroma_db import ChromaDb
from scripts.benchmark.helpers import first_keyword_rank, top_documents, write_report

logger = logging.getLogger("benchmark.grounding")

TOPIC = "bench_grounding"
DOCS_FOLDER = "data/documents/dask"
EMBED_MODEL = "nomic-embed-text"
MAX_WORDS = 500
OVERLAP = 0
TOP_N = 20
RUNS_DIR = Path("benchmark/runs")

# The five queries; all should surface the same "groupby" chunk.
GROUPBY_QUERIES = {
    "Q1 parallelize groupby": "parallelize groupby",
    "Q2 whole question": "in dask, how to parallelize a groupby?",
    "Q3 keyword": "groupby",
    "Q4 paraphrase": "group by a column and aggregate",
}
# Generalization: the winner is not overfit to groupby (rank of the API term).
GENERALIZATION = {
    "read a CSV into a dask dataframe": "read_csv",
    "persist a dask dataframe in memory": "persist",
    "merge two dask dataframes": "merge",
    "repartition a dask dataframe": "repartition",
}

Ranks = dict[str, int | None]


def index(ollama_url: str) -> ChromaDb:
    """Reindex the dask corpus into the throwaway topic with the winning configuration."""
    db = ChromaDb(
        embed_model=EMBED_MODEL,
        ollama_url=f"{ollama_url}/api/embeddings",
        max_words=MAX_WORDS,
        overlap=OVERLAP,
    )
    db.reset_collection(TOPIC)
    db.index_folder(DOCS_FOLDER, TOPIC)
    return db


def measure(db: ChromaDb) -> tuple[Ranks, Ranks]:
    """Return the groupby-query ranks and the generalization ranks."""
    groupby_ranks: Ranks = {
        label: first_keyword_rank(top_documents(db, TOPIC, query, TOP_N), "groupby")
        for label, query in GROUPBY_QUERIES.items()
    }
    generalization_ranks: Ranks = {
        question: first_keyword_rank(top_documents(db, TOPIC, question, TOP_N), keyword)
        for question, keyword in GENERALIZATION.items()
    }
    return groupby_ranks, generalization_ranks


def run(ollama_url: str) -> tuple[Ranks, Ranks]:
    """Index, measure, clean up and write the report; return the two rank maps."""
    db = index(ollama_url)
    try:
        groupby_ranks, generalization_ranks = measure(db)
    finally:
        db.reset_collection(TOPIC)
    _report(groupby_ranks, generalization_ranks)
    return groupby_ranks, generalization_ranks


def _report(groupby_ranks: Ranks, generalization_ranks: Ranks) -> Path:
    """Write the ranks to benchmark/runs, returning the path."""
    rows = "\n".join(f"| {label} | {rank} |" for label, rank in groupby_ranks.items())
    gen_rows = "\n".join(
        f"| {question} | {keyword} | {generalization_ranks[question]} |"
        for question, keyword in GENERALIZATION.items()
    )
    path = RUNS_DIR / "grounding-nomic-w500.md"
    write_report(
        path,
        f"grounding - {EMBED_MODEL}, MAX_WORDS={MAX_WORDS}, OVERLAP={OVERLAP}",
        [
            (
                "groupby queries (rank of first 'groupby' chunk in top-20)",
                f"| query | rank |\n|---|---|\n{rows}",
            ),
            (
                "generalization (rank of first chunk with the API term)",
                f"| question | keyword | rank |\n|---|---|---|\n{gen_rows}",
            ),
        ],
    )
    return path


def main() -> None:
    """Run the grounding benchmark and log the ranks."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", force=True)
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    groupby_ranks, generalization_ranks = run(ollama_url)
    logger.info("groupby ranks: %s", groupby_ranks)
    logger.info("generalization ranks: %s (see benchmark/runs)", generalization_ranks)


if __name__ == "__main__":
    main()
