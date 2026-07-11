# multi-agent - llama3.2:3b

## summary

routing accuracy (right specialist) 60% (6/10)

## per case

| case | expected | correct | routed to |
|---|---|---|---|
| python | python_expert | 4/5 | python_expert, python_expert, python_expert, triage, python_expert |
| aws | aws_expert | 2/5 | aws_expert, triage, triage, triage, aws_expert |
