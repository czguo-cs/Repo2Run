#!/bin/bash
source setup_env.sh
# 使用4个并行worker评估
python3 evaluation/evaluate_results.py \
    --output_dir output/benchmark_python_3.0_repo2run_v2 \
    --benchmark_file benchmark_python_3.0_repo2run.jsonl \
    --parallel 15 \
    --timeout 1000
