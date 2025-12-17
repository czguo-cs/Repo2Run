#!/bin/bash
export OPENAI_API_BASE_URL="http://yy.dbh.baidu-int.com/v1"
export OPENAI_KEY="sk-WRdpcxwBFvnUWaE6IUqepIBmBZE2jQCC3xAWVuhGXF4am4Fe"

# 设置代理以便 git clone 能够访问 GitHub
export http_proxy=http://iJbVyX:mJ8eR9tU6%5Bs@10.251.112.51:8799
export https_proxy=http://iJbVyX:mJ8eR9tU6%5Bs@10.251.112.51:8799

output_dir="benchmark_5.0_python_repo2run"
rm -rf "output/${output_dir}"
rm -rf utils

python build_agent/multi_main.py dataset/benchmark_5.0_python_commands.txt --output_dir "${output_dir}"
