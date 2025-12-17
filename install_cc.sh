#!/bin/bash

# ==============================================================================
# 脚本功能: 自动化配置 Conda 环境、安装依赖包并配置 Claude 代码助手
# 适用场景: 新环境初始化或 Claude 开发环境快速部署
# 注意事项: 
#   1. 需提前安装 Conda (Miniconda3 推荐)
#   2. 脚本会修改 ~/.bashrc 文件添加环境自动激活
#   3. Claude 配置文件会覆盖现有 ~/.claude/settings.json
# ==============================================================================

# -------------------------- 基础环境配置 --------------------------
# 初始化 Conda (对所有终端生效)
# 激活目标 Conda 环境 (若不存在会报错, 需提前创建: conda create -n testbed python=3.10)
# -------------------------- 依赖包安装 --------------------------
# 安装 Node.js 20 (conda-forge 源)
echo "=== 安装 Node.js 20 ==="
conda install -c conda-forge -y nodejs=20

# 升级 pip 并安装 Python 依赖
echo "=== 安装 Python 依赖包 ==="
pip install --upgrade pip setuptools wheel claude_agent_sdk

# 安装 Claude Code CLI (指定版本)
echo "=== 安装 Claude Code CLI ==="
npm install -g @anthropic-ai/claude-code@2.0.36

# -------------------------- 环境自动激活配置 --------------------------
echo "=== 配置终端自动激活 Conda 环境 ==="
# 避免重复添加配置
# -------------------------- Claude 配置 --------------------------
echo "=== 配置 Claude 代码助手 ==="
# 创建 Claude 配置目录
mkdir -p ~/.claude


cat > ~/.claude/settings.json << 'EOF'
{
  "apiKeyHelper": "~/.claude/anthropic_key.sh",
  "env": {
    "ANTHROPIC_BASE_URL": "http://10.214.54.151:8080",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": 1,
    "ANTHROPIC_MODEL": "claude-sonnet-4-5-20250929",
    "ANTHROPIC_SMALL_FAST_MODEL": "claude-haiku-4-5-20251001-v1:0",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-5-20250929",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-sonnet-4-5-20250929",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5-20251001-v1:0"
  }
}
EOF

echo "echo \"ernie-code-cc-special\"" > ~/.claude/anthropic_key.sh

chmod +x ~/.claude/anthropic_key.sh

mkdir -p ~/.claude/commands
echo "1570698d-5d71-4229-a0a7-c24d8b6eeaaf" > ~/.claude/commands/good-session.md
echo "1d862f69-238f-49f1-b64e-77ea0859c811" > ~/.claude/commands/bad-session.md

# -------------------------- 完成提示 --------------------------
echo "=================================================="
echo "Claude 开发环境配置完成!"
echo "请执行以下操作使配置生效:"
echo "1. 关闭当前终端并重新打开 (激活 Conda 自动激活)"
echo "2. 验证 Claude 配置: claude-code --version"
echo "3. 验证 API 连接: claude-code chat"
echo "=================================================="
