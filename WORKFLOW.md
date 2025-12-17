# Repo2Run 工作流程说明

## 📋 脚本概览

项目现在分为三个独立的阶段脚本：

```
run1_prepare.sh       数据准备（转换原始数据）
       ↓
run2.sh               环境构建（构建 Docker 环境）
       ↓
run3_evaluation.sh    结果评估（评估构建结果）
```

## 🔄 完整工作流程

### 阶段 1: 数据准备 (run1_prepare.sh)

**功能：**
- 读取原始 benchmark 数据
- 转换并添加必需字段
- 生成两个输出文件

**输入：**
```
dataset/benchmark_python_v3.0.jsonl   (原始数据)
```

**输出：**
```
dataset/benchmark_python_3.0_repo2run.jsonl   (完整数据)
dataset/commands.txt                          (命令列表)
```

**执行：**
```bash
./run1_prepare.sh
# 或指定 LLM 模型
./run1_prepare.sh --llm gpt-4o-2024-05-13
```

---

### 阶段 2: 环境构建 (run2.sh)

**功能：**
- 读取 commands.txt 中的命令
- 并行运行多个构建任务
- 生成 Dockerfile 和构建结果

**输入：**
```
dataset/commands.txt   (来自阶段1)
```

**输出：**
```
output/benchmark_python_3.0_repo2run/
  ├── {instance_id}/
  │   ├── Dockerfile
  │   ├── run.log
  │   └── ...
  └── ...
```

**执行：**
```bash
./run2.sh
```

---

### 阶段 3: 结果评估 (run3_evaluation.sh)

**功能：**
- 构建 Docker 镜像
- 运行测试用例
- 生成评估报告

**输入：**
```
output/benchmark_python_3.0_repo2run/     (来自阶段2)
dataset/benchmark_python_3.0_repo2run.jsonl   (来自阶段1)
```

**输出：**
```
output/evaluation_results_benchmark_python_3.0_repo2run.json
```

**执行：**
```bash
./run3_evaluation.sh
```

---

## 🚀 快速开始

### 方式一：逐步执行（推荐用于调试）

```bash
# 步骤 1: 准备数据
./run1_prepare.sh

# 检查输出
ls -lh dataset/benchmark_python_3.0_repo2run.jsonl
ls -lh dataset/commands.txt

# 步骤 2: 构建环境
./run2.sh

# 监控进度
tail -f output/benchmark_python_3.0_repo2run/{instance_id}/run.log

# 步骤 3: 评估结果
./run3_evaluation.sh

# 查看结果
cat output/evaluation_results_*.json | jq .statistics
```

### 方式二：一键执行

```bash
# 执行所有步骤
./run1_prepare.sh && ./run2.sh && ./run3_evaluation.sh
```

---

## 📊 数据流转

```
原始数据 (dataset/benchmark_python_v3.0.jsonl)
    |
    | [run1_prepare.sh]
    | 添加: full_name, sha, root_path, llm
    |
    +--> dataset/benchmark_python_3.0_repo2run.jsonl
    |    (供评估使用)
    |
    +--> dataset/commands.txt
         (供构建使用)
         |
         | [run2.sh]
         | 执行构建命令
         |
         +--> output/benchmark_python_3.0_repo2run/
              (构建结果)
              |
              | [run3_evaluation.sh]
              | 评估构建结果
              |
              +--> output/evaluation_results_*.json
                   (评估报告)
```

---

## ⚙️ 配置说明

### run1_prepare.sh 配置

可通过命令行参数或修改脚本开头的变量：

```bash
INPUT_DATA="dataset/benchmark_python_v3.0.jsonl"
OUTPUT_JSONL="dataset/benchmark_python_3.0_repo2run.jsonl"
OUTPUT_COMMANDS="dataset/commands.txt"
LLM_MODEL="kimi-k2-instruct"
```

### run2.sh 配置

修改脚本中的变量：

```bash
output_dir="benchmark_python_3.0_repo2run"
export OPENAI_API_BASE_URL="..."
export OPENAI_KEY="..."
```

### run3_evaluation.sh 配置

修改脚本中的参数：

```bash
--output_dir output/benchmark_python_3.0_repo2run
--benchmark_file dataset/benchmark_python_3.0_repo2run.jsonl
--parallel 15
--timeout 1000
```

---

## 🔍 常见场景

### 场景 1: 只想准备数据

```bash
./run1_prepare.sh
# 检查生成的文件
cat dataset/commands.txt
```

### 场景 2: 重新构建环境（数据已准备好）

```bash
# 跳过阶段1，直接运行阶段2
./run2.sh
```

### 场景 3: 重新评估结果（环境已构建好）

```bash
# 跳过阶段1和2，直接运行阶段3
./run3_evaluation.sh
```

### 场景 4: 使用不同的 LLM 模型

```bash
# 阶段1使用指定模型
./run1_prepare.sh --llm gpt-4o-2024-05-13

# 阶段2和3正常执行
./run2.sh
./run3_evaluation.sh
```

### 场景 5: 测试小规模数据

```bash
# 创建测试数据
head -10 dataset/benchmark_python_v3.0.jsonl > test.jsonl

# 使用测试数据
./run1_prepare.sh \
  --input test.jsonl \
  --output_jsonl dataset/test_output.jsonl \
  --output_commands dataset/test_commands.txt

# 修改 run2.sh 中的路径后执行
# ...
```

---

## 📁 目录结构

```
Repo2Run/
├── dataset/
│   ├── benchmark_python_v3.0.jsonl              # 原始数据
│   ├── benchmark_python_3.0_repo2run.jsonl      # 转换后的完整数据
│   └── commands.txt                              # 命令列表
├── output/
│   ├── benchmark_python_3.0_repo2run/           # 构建结果
│   │   ├── {instance_id}/
│   │   │   ├── Dockerfile
│   │   │   ├── run.log
│   │   │   └── evaluation_logs/
│   │   └── ...
│   └── evaluation_results_*.json                 # 评估报告
├── run1_prepare.sh                               # 数据准备脚本
├── run2.sh                                       # 环境构建脚本
├── run3_evaluation.sh                            # 结果评估脚本
├── prepare_benchmark.py                          # 核心转换脚本
└── USAGE_GUIDE.md                                # 详细使用指南
```

---

## ❓ 故障排查

### 问题 1: run1_prepare.sh 失败

- 检查输入文件是否存在
- 检查 prepare_benchmark.py 是否存在
- 查看错误信息

### 问题 2: run2.sh 失败

- 确认 dataset/commands.txt 已生成
- 检查 API Key 配置
- 查看 run.log 日志

### 问题 3: run3_evaluation.sh 失败

- 确认构建结果目录存在
- 确认 benchmark JSONL 文件存在
- 查看 evaluation_logs/ 中的日志

---

## 💡 提示

1. **并行执行**: run2.sh 和 run3_evaluation.sh 都支持并行，可根据机器性能调整
2. **增量构建**: 可以只重新运行失败的实例
3. **日志查看**: 每个阶段都有详细的日志输出
4. **灵活配置**: run1_prepare.sh 支持命令行参数，方便测试

---

## 📞 获取更多帮助

- 查看 USAGE_GUIDE.md 获取详细文档
- 运行 `./run1_prepare.sh --help` 查看帮助
- 查看日志文件定位问题
