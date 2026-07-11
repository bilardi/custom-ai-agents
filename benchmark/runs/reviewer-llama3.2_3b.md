# reviewer - llama3.2:3b

## summary

task: `Write Dask code to parallelize a groupby aggregation on a DataFrame.`

catch rate (invented-api, higher better) 100%; false-positive rate (correct cases, lower better) 100%; generic-answer flag rate (grounding call, for discussion) 80%

## per case

| case | expected | flagged |
|---|---|---|
| invented-api | flag | 10/10 |
| good-grounded | ok | 10/10 |
| valid-variation | ok | 10/10 |
| generic-ungrounded | generic | 8/10 |
