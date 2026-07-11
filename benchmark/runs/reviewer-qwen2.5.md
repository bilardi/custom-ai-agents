# reviewer - qwen2.5

## summary

task: `Write Dask code to parallelize a groupby aggregation on a DataFrame.`

catch rate (invented-api, higher better) 60%; false-positive rate (correct cases, lower better) 0%; generic-answer flag rate (grounding call, for discussion) 0%

## per case

| case | expected | flagged |
|---|---|---|
| invented-api | flag | 6/10 |
| good-grounded | ok | 0/10 |
| valid-variation | ok | 0/10 |
| generic-ungrounded | generic | 0/10 |
