# Grounding benchmark: retrieval quality

Test question: "in dask, how to parallelize a groupby?". The right content is in
the index (the "Dask DataFrame" PDF, examples like
`ddf.groupby("Origin").DepDelay.mean().compute()`), but retrieval did not bring
it to the top. Metric: the 0-based rank of the first chunk containing "groupby"
within the top-20 results ("-" if absent). The rank shows which `TOP_K` would be
needed.

Fixed queries:

- Q1 `parallelize groupby` (the one the agent chose in the real run)
- Q2 `in dask, how to parallelize a groupby?` (the whole question)
- Q3 `groupby` (keyword)
- Q4 `group by a column and aggregate` (paraphrase)

## Results (rank of first groupby chunk in top-20)

| # | config | Q1 | Q2 | Q3 | Q4 | note |
|---|---|---|---|---|---|---|
| 1 | qwen3, MAX_WORDS=300 (baseline) | 6 | 15 | 15 | 6 | `TOP_K=3` loses everything; needs >=7 (Q1/Q4), >=16 (Q2/Q3) |
| 2 | qwen3, MAX_WORDS=150 | - | - | - | 10 | 112 chunks, 134s; small chunks are worse (groupby signal diluted) |
| 3 | qwen3, MAX_WORDS=500 | 3 | 0 | 1 | 3 | 37 chunks, 108s; large chunks help a lot; `TOP_K=4` is enough for all queries |
| 4 | nomic-embed-text, MAX_WORDS=300 | 2 | 1 | 6 | 4 | 58 chunks, 15.2s (7-9x faster than qwen3); beats qwen3 w300 on all |
| 5 | nomic-embed-text, MAX_WORDS=150 | 1 | 1 | - | 3 | 112 chunks, 11.2s; small chunks stay weak even with nomic |
| 6 | nomic-embed-text, MAX_WORDS=500 | 0 | 0 | 0 | 1 | 37 chunks, 8.1s; best overall, `TOP_K=2` is enough for all queries |

Row 6 (the winner) is reproduced by `scripts.benchmark.grounding`; the qwen3 rows and the
smaller chunk sizes are documented exploration, not re-run by the test.

## Conclusions

Two independent levers that add up:

- chunk size: large chunks (w500) are much better than small ones (w150), for both embedders. Counter-intuitive versus "small chunks = more precise": here the groupby examples stay together with the context that makes them meaningful, and with fewer chunks there is less signal dilution
- embedder: `nomic-embed-text` (a retrieval-dedicated model) beats `qwen3` (a general LLM used as an embedder) at every chunk size, and indexes about 10x faster (8-15s versus 108-134s)

Winner (embedder + chunk): `nomic-embed-text` + `MAX_WORDS=500`, ranks 0/0/0/1,
`TOP_K=2` sufficient. The baseline (qwen3, w300, `TOP_K=3`) retrieved nothing;
combining the two levers brings groupby to the top.

## Third lever: chunk overlap

`chunk_text` accepts an `overlap` (stride = max_words - overlap). Comparison with nomic:

| config | Q1 | Q2 | Q3 | Q4 | chunks | note |
|---|---|---|---|---|---|---|
| nomic, w500, overlap 0 | 0 | 0 | 0 | 1 | 37 | winner |
| nomic, w500, overlap 100 | 0 | 1 | 7 | 9 | 43 | worse: near-duplicate chunks compete and lower the rank |
| nomic, w500, overlap 250 | 0 | 2 | 0 | 3 | 62 | recovers Q3 but worsens Q2/Q4; needs TOP_K=4 instead of 2 |
| nomic, w150, overlap 0 | 1 | 1 | - | 3 | 112 | Q3 absent |
| nomic, w150, overlap 50 | 1 | 2 | 3 | 0 | 164 | overlap recovers Q3 (from absent to rank 3) |

Insight: overlap helps when chunks are small and a passage is cut at the
boundary (it recovers the fragmented case), but on already-large chunks it is
counterproductive: it adds near-duplicate chunks that compete and lower the
rank of the best one. The rule is not "always overlap" but "overlap when chunks
are small relative to the passage to keep together". With large chunks (w500)
the passage already fits, and overlap 0 is best. This whole table is documented
exploration, not re-run by the test.

## Generalization: pandas questions (not groupby)

Check that the winner (nomic, w500) is not overfit to the groupby question. Real
dask index, other dataframe operations (rank of the first chunk with the API term):

| question | keyword | rank |
|---|---|---|
| read a CSV into a dask dataframe | read_csv | 0 |
| persist a dask dataframe in memory | persist | 0 |
| merge two dask dataframes | merge | 1 |
| repartition a dask dataframe | repartition | 7 |

The config generalizes: 3 of 4 at rank 0-1. The only weak one (`repartition`,
rank 7) is a corpus-coverage problem (the term appears only twice in the docs,
few chunks), not a configuration one. The lever for rare topics is `TOP_K`, not
the embedder or chunk size. Confirmation: embedder and chunk size are general
levers; `TOP_K` and corpus coverage are the per-topic tuning. This table is
reproduced by `scripts.benchmark.grounding` (its test asserts at least 3 of 4 in the top 2).

## Final decision

Adopt: embedder `nomic-embed-text`, `MAX_WORDS=500`, `OVERLAP=0`, small `TOP_K`
(2-3). Overlap stays an implemented, available lever, useful for corpora/chunks
where a passage gets fragmented.
