# multi-agent - qwen2.5

## summary

routing accuracy (right specialist) 90% (9/10)

## per case

| case | expected | correct | routed to |
|---|---|---|---|
| python | python_expert | 5/5 | python_expert, python_expert, python_expert, python_expert, python_expert |
| aws | aws_expert | 4/5 | aws_expert, aws_expert, triage, aws_expert, aws_expert |
