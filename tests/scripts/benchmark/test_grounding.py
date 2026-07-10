"""Test the grounding benchmark: the winning config ranks the target chunk high.

Retrieval is deterministic, so this is a reproducible regression. See
benchmark/grounding.md for the exploration behind the winner.
"""

import pytest

from scripts.benchmark import grounding

pytestmark = pytest.mark.benchmark


def test_grounding_winner_ranks_target_chunk_high(ollama_url, require_model):
    require_model(grounding.EMBED_MODEL)
    groupby_ranks, generalization_ranks = grounding.run(ollama_url)

    # nomic + w500 brings the groupby chunk to the top for every query.
    for label, rank in groupby_ranks.items():
        assert rank is not None, f"{label}: no groupby chunk in top-{grounding.TOP_N}"
        assert rank <= 3, f"{label}: rank {rank}"
    # the config generalizes: at least 3 of 4 dataframe ops rank in the top 2.
    in_top2 = sum(1 for rank in generalization_ranks.values() if rank is not None and rank <= 1)
    assert in_top2 >= 3, generalization_ranks
