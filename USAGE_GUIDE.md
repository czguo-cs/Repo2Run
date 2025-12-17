# Repo2Run 使用指南

## 📖 概述

本指南说明如何使用数据转换脚本，从原始 benchmark 数据到完整的环境构建和评估流程。

## 🎯 快速开始

### 方式一：一键执行（推荐）

```bash
./run_all.sh
```

这个脚本会自动完成以下所有步骤：
1. 数据转换
2. 环境构建
3. 结果评估

### 方式二：分步执行

#### 第 1 步：准备数据

```bash
python3 prepare_benchmark.py \
  --input dataset/benchmark_python_v3.0.jsonl \
  --output_jsonl benchmark_python_3.0_repo2run.jsonl \
  --output_commands commands.txt \
  --llm "kimi-k2-instruct"
```

**参数说明：**
- `--input`: 原始数据文件路径
- `--output_jsonl`: 输出的完整 benchmark JSONL 文件（供评估使用）
- `--output_commands`: 输出的命令文件（供 run.sh 使用）
- `--root_path`: 项目根路径（可选，默认为当前目录）
- `--llm`: LLM 模型名称（可选，默认为 gpt-4o-2024-05-13）

#### 第 2 步：构建环境

```bash
./run.sh
```

这会：
- 读取 `commands.txt` 中的命令
- 并行运行多个构建任务
- 将结果保存到 `output/benchmark_python_3.0_repo2run_v2/` 目录

#### 第 3 步：评估结果

```bash
./run_evaluation.sh
```

这会：
- 构建 Docker 镜像
- 运行测试用例
- 生成评估报告

## 📁 文件结构

```
Repo2Run/
├── dataset/
│   └── benchmark_python_v3.0.jsonl          # 原始数据
├── prepare_benchmark.py                      # 数据转换脚本
├── run_all.sh                                # 一键执行脚本
├── run.sh                                    # 环境构建脚本
├── run_evaluation.sh                         # 评估脚本
├── benchmark_python_3.0_repo2run.jsonl      # 生成的完整数据
├── commands.txt                              # 生成的命令列表
└── output/
    └── benchmark_python_3.0_repo2run_v2/    # 构建结果
        ├── {instance_id}/                    # 每个实例的结果
        │   ├── Dockerfile
        │   ├── run.log
        │   └── evaluation_logs/
        └── evaluation_results_*.json         # 评估报告
```

## 🔧 高级配置

### 自定义 LLM 模型

修改 `prepare_benchmark.py` 的 `--llm` 参数：

```bash
python3 prepare_benchmark.py \
  --input dataset/benchmark_python_v3.0.jsonl \
  --llm "gpt-4o-2024-05-13"  # 或其他模型
```

或者修改 `run_all.sh` 中的 `LLM_MODEL` 变量：

```bash
# 编辑 run_all.sh
LLM_MODEL="your-model-name"
```

### 自定义输出目录

修改 `run.sh` 中的 `output_dir` 变量：

```bash
# 编辑 run.sh
output_dir="your_output_dir_name"
```

### 自定义评估参数

修改 `run_evaluation.sh` 中的参数：

```bash
# 编辑 run_evaluation.sh
--parallel 15       # 并行数
--timeout 1000      # 超时时间（秒）
```

## 🔍 数据格式说明

### 原始数据格式

`dataset/benchmark_python_v3.0.jsonl` 包含以下字段：

```json
{
  "repo": "quantumlib/Cirq",
  "instance_id": "quantumlib__Cirq-3015",
  "base_commit": "d998b3afe20dd6783e00dcc2590ba0f162b95af7",
  "patch": "...",
  "test_patch": "...",
  ...
}
```

### 转换后的数据格式

`benchmark_python_3.0_repo2run.jsonl` 增加了以下字段：

```json
{
  "repo": "quantumlib/Cirq",
  "instance_id": "quantumlib__Cirq-3015",
  "base_commit": "d998b3afe20dd6783e00dcc2590ba0f162b95af7",
  "patch": "...",
  "test_patch": "...",
  "full_name": "quantumlib/Cirq",           # 新增
  "sha": "d998b3afe20dd6783e00dcc2590ba0f162b95af7",  # 新增
  "root_path": "/path/to/Repo2Run",         # 新增
  "llm": "kimi-k2-instruct",                # 新增
  ...
}
```

## 📊 输出说明

### 构建结果

每个实例的构建结果保存在：
```
output/benchmark_python_3.0_repo2run_v2/{instance_id}/
├── Dockerfile          # 生成的 Dockerfile
├── run.log             # 构建日志
├── track.json          # 构建轨迹
└── ...
```

### 评估结果

评估报告保存在：
```
output/evaluation_results_benchmark_python_3.0_repo2run_v2.json
```

包含以下信息：
- 总体统计（通过率、失败率等）
- 每个实例的详细结果
- 失败原因分类

## ❓ 常见问题

### Q1: 如何只处理部分数据？

可以手动创建包含部分数据的文件：

```bash
head -10 dataset/benchmark_python_v3.0.jsonl > test_data.jsonl
python3 prepare_benchmark.py --input test_data.jsonl ...
```

### Q2: 转换脚本失败怎么办？

检查：
1. 输入文件是否存在
2. 数据格式是否正确（每行是一个有效的 JSON）
3. 必需字段是否存在（repo, instance_id, base_commit）

### Q3: 如何更改 API Key？

修改 `run.sh` 和 `run_evaluation.sh` 中的环境变量：

```bash
export OPENAI_API_BASE_URL="your-api-url"
export OPENAI_KEY="your-api-key"
```

### Q4: 评估脚本运行很慢怎么办？

可以调整并行数：

```bash
# 在 run_evaluation.sh 中修改
--parallel 20  # 增加并行数（根据机器性能调整）
```

## 📝 示例工作流

### 完整流程示例

```bash
# 1. 准备数据
python3 prepare_benchmark.py \
  --input dataset/benchmark_python_v3.0.jsonl \
  --output_jsonl benchmark_python_3.0_repo2run.jsonl \
  --output_commands commands.txt \
  --llm "kimi-k2-instruct"

# 2. 检查生成的文件
wc -l commands.txt
head -1 benchmark_python_3.0_repo2run.jsonl | jq .

# 3. 构建环境
./run.sh

# 4. 等待构建完成，查看日志
tail -f output/benchmark_python_3.0_repo2run_v2/{instance_id}/run.log

# 5. 评估结果
./run_evaluation.sh

# 6. 查看评估报告
cat output/evaluation_results_benchmark_python_3.0_repo2run_v2.json | jq .statistics
```

### 测试小规模数据

```bash
# 创建测试数据（前 5 条）
head -5 dataset/benchmark_python_v3.0.jsonl > test.jsonl

# 转换
python3 prepare_benchmark.py \
  --input test.jsonl \
  --output_jsonl test_output.jsonl \
  --output_commands test_commands.txt

# 查看结果
cat test_commands.txt
```

## 🚀 性能优化建议

1. **并行构建**: `run.sh` 默认使用 5 个并行进程，可以根据机器性能调整
2. **并行评估**: `run_evaluation.sh` 默认使用 15 个并行进程，可以调整
3. **磁盘空间**: 确保有足够的磁盘空间存储 Docker 镜像和构建结果
4. **内存管理**: 注意监控内存使用，必要时减少并行数

## 📞 获取帮助

如果遇到问题，可以：

1. 查看日志文件：`output/{output_dir}/{instance_id}/run.log`
2. 查看评估日志：`output/{output_dir}/{instance_id}/evaluation_logs/`
3. 检查数据格式：使用 `jq` 工具查看 JSON 文件
4. 查看脚本帮助：`python3 prepare_benchmark.py --help`

## 📄 许可证

Apache-2.0
