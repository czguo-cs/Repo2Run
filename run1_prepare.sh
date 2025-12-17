#!/bin/bash
# Repo2Run 数据准备脚本
# 功能：将原始 benchmark 数据转换为 Repo2Run 所需格式

set -e  # 遇到错误立即退出

# ==================== 配置区域 ====================
# 原始数据文件（Python语言筛选后的数据）
INPUT_DATA="dataset/benchmark_v5.0.python.jsonl"

# 输出文件
OUTPUT_JSONL="dataset/benchmark_5.0_python_repo2run.jsonl"
OUTPUT_COMMANDS="dataset/benchmark_5.0_python_commands.txt"

# 项目根路径（默认当前目录）
ROOT_PATH=$(pwd)

# LLM 模型
LLM_MODEL="kimi-k2-instruct"

# ==================== 参数解析 ====================
# 支持命令行参数覆盖默认配置
while [[ $# -gt 0 ]]; do
    case $1 in
        --input)
            INPUT_DATA="$2"
            shift 2
            ;;
        --output_jsonl)
            OUTPUT_JSONL="$2"
            shift 2
            ;;
        --output_commands)
            OUTPUT_COMMANDS="$2"
            shift 2
            ;;
        --root_path)
            ROOT_PATH="$2"
            shift 2
            ;;
        --llm)
            LLM_MODEL="$2"
            shift 2
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --input FILE              原始数据文件路径 (默认: dataset/benchmark_v5.0.python.jsonl)"
            echo "  --output_jsonl FILE       输出 JSONL 文件路径 (默认: dataset/benchmark_5.0_python_repo2run.jsonl)"
            echo "  --output_commands FILE    输出命令文件路径 (默认: dataset/benchmark_5.0_python_commands.txt)"
            echo "  --root_path PATH          项目根路径 (默认: 当前目录)"
            echo "  --llm MODEL               LLM 模型名称 (默认: kimi-k2-instruct)"
            echo "  -h, --help                显示此帮助信息"
            echo ""
            echo "示例:"
            echo "  $0"
            echo "  $0 --llm gpt-4o-2024-05-13"
            echo "  $0 --input custom_data.jsonl --llm claude-3-sonnet"
            exit 0
            ;;
        *)
            echo "错误: 未知参数 '$1'"
            echo "使用 '$0 --help' 查看帮助"
            exit 1
            ;;
    esac
done

# ==================== 脚本开始 ====================

echo "================================================================================"
echo "                    Repo2Run 数据准备脚本"
echo "================================================================================"
echo ""
echo "配置信息:"
echo "  - 原始数据:     ${INPUT_DATA}"
echo "  - 输出 JSONL:   ${OUTPUT_JSONL}"
echo "  - 输出命令:     ${OUTPUT_COMMANDS}"
echo "  - 项目根路径:   ${ROOT_PATH}"
echo "  - LLM 模型:     ${LLM_MODEL}"
echo ""
echo "================================================================================"
echo ""

# 检查原始数据是否存在
if [ ! -f "${INPUT_DATA}" ]; then
    echo "❌ 错误: 原始数据文件不存在: ${INPUT_DATA}"
    exit 1
fi

# 检查转换脚本是否存在
if [ ! -f "prepare_benchmark.py" ]; then
    echo "❌ 错误: 转换脚本不存在: prepare_benchmark.py"
    exit 1
fi

# 创建输出目录（如果不存在）
OUTPUT_DIR=$(dirname "${OUTPUT_JSONL}")
if [ ! -d "${OUTPUT_DIR}" ]; then
    mkdir -p "${OUTPUT_DIR}"
    echo "✓ 创建输出目录: ${OUTPUT_DIR}"
    echo ""
fi

# ==================== 数据转换 ====================
echo "正在执行数据转换..."
echo ""

python3 prepare_benchmark.py \
    --input "${INPUT_DATA}" \
    --output_jsonl "${OUTPUT_JSONL}" \
    --output_commands "${OUTPUT_COMMANDS}" \
    --root_path "${ROOT_PATH}" \
    --llm "${LLM_MODEL}"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 数据转换失败"
    exit 1
fi

echo ""
echo "================================================================================"
echo "✅ 数据准备完成！"
echo "================================================================================"
echo ""
echo "生成的文件:"
echo "  ✓ ${OUTPUT_JSONL}"
echo "  ✓ ${OUTPUT_COMMANDS}"
echo ""
echo "文件统计:"
if [ -f "${OUTPUT_JSONL}" ]; then
    JSONL_COUNT=$(wc -l < "${OUTPUT_JSONL}")
    echo "  - JSONL 记录数: ${JSONL_COUNT}"
fi
if [ -f "${OUTPUT_COMMANDS}" ]; then
    CMD_COUNT=$(wc -l < "${OUTPUT_COMMANDS}")
    echo "  - 命令总数:     ${CMD_COUNT}"
fi
echo ""
echo "接下来你可以:"
echo "  1. 执行 run2.sh 来构建环境（如果存在）"
echo "  2. 执行 run3_evaluation.sh 来评估结果（如果存在）"
echo "  3. 或者执行 ./run.sh 来构建环境"
echo ""
echo "================================================================================"
