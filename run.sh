#!/bin/bash
export OPENAI_API_BASE_URL="**"
export OPENAI_KEY="sk-**"

output_dir="benchmark_python_3.0_repo2run_v2"
rm -rf "output/${output_dir}"
rm -rf utils
python build_agent/multi_main.py commands.txt --output_dir "${output_dir}"
