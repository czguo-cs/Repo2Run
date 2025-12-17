#!/bin/bash
export OPENAI_API_BASE_URL="http://yy.dbh.baidu-int.com/v1"
export OPENAI_KEY="sk-WRdpcxwBFvnUWaE6IUqepIBmBZE2jQCC3xAWVuhGXF4am4Fe"

# 使用15个并行worker评估Python语言的benchmark数据
python3 evaluation/evaluate_results.py \
    --output_dir output/benchmark_5.0_python_repo2run \
    --benchmark_file dataset/benchmark_5.0_python_repo2run.jsonl \
    --parallel 15 \
    --timeout 1000
