# grounding - nomic-embed-text, MAX_WORDS=500, OVERLAP=0

## groupby queries (rank of first 'groupby' chunk in top-20)

| query | rank |
|---|---|
| Q1 parallelize groupby | 0 |
| Q2 whole question | 0 |
| Q3 keyword | 0 |
| Q4 paraphrase | 1 |

## generalization (rank of first chunk with the API term)

| question | keyword | rank |
|---|---|---|
| read a CSV into a dask dataframe | read_csv | 0 |
| persist a dask dataframe in memory | persist | 0 |
| merge two dask dataframes | merge | 1 |
| repartition a dask dataframe | repartition | 7 |
