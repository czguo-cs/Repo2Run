#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据转换脚本：将原始 benchmark 数据转换为 Repo2Run 所需格式

功能：
1. 读取原始 benchmark JSONL 文件
2. 转换并补充必要字段
3. 生成完整的 benchmark JSONL 文件
4. 生成 commands.txt 文件供 run.sh 使用
"""

import argparse
import json
import os
import sys


def load_original_data(input_file):
    """
    加载原始 benchmark 数据

    Args:
        input_file: 原始数据文件路径

    Returns:
        List[dict]: 数据列表
    """
    data_list = []

    if not os.path.exists(input_file):
        print(f"错误: 输入文件不存在: {input_file}")
        sys.exit(1)

    with open(input_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                data_list.append(data)
            except json.JSONDecodeError as e:
                print(f"警告: 第 {line_num} 行 JSON 解析失败: {e}")
                continue

    return data_list


def transform_data(data_list, root_path, llm_model):
    """
    转换数据格式，添加缺失字段

    Args:
        data_list: 原始数据列表
        root_path: 项目根路径
        llm_model: LLM 模型名称

    Returns:
        List[dict]: 转换后的数据列表
    """
    transformed_list = []
    skipped_count = 0

    for idx, data in enumerate(data_list, 1):
        # 检查必需字段
        if 'repo' not in data:
            print(f"警告: 第 {idx} 条数据缺少 'repo' 字段，跳过")
            skipped_count += 1
            continue

        if 'instance_id' not in data:
            print(f"警告: 第 {idx} 条数据缺少 'instance_id' 字段，跳过")
            skipped_count += 1
            continue

        # 创建新的数据对象（保留所有原始字段）
        new_data = data.copy()

        # 添加或映射必需字段
        new_data['full_name'] = data.get('repo')

        # sha 字段：优先使用 base_commit，如果没有则使用 sha
        if 'base_commit' in data:
            new_data['sha'] = data['base_commit']
        elif 'sha' not in new_data:
            print(f"警告: 第 {idx} 条数据缺少 'sha' 和 'base_commit' 字段，跳过")
            skipped_count += 1
            continue

        # 添加配置字段
        new_data['root_path'] = root_path
        new_data['llm'] = llm_model

        transformed_list.append(new_data)

    if skipped_count > 0:
        print(f"\n共跳过 {skipped_count} 条无效数据")

    return transformed_list


def generate_commands(data_list, root_path, llm_model):
    """
    生成 commands.txt 内容

    Args:
        data_list: 数据列表
        root_path: 项目根路径
        llm_model: LLM 模型名称

    Returns:
        List[str]: 命令列表
    """
    commands = []

    for data in data_list:
        full_name = data.get('full_name')
        sha = data.get('sha')
        instance_id = data.get('instance_id')

        if not all([full_name, sha, instance_id]):
            print(f"警告: 数据不完整，跳过命令生成: {data.get('instance_id', 'unknown')}")
            continue

        # 生成命令行
        cmd = (
            f'python -u build_agent/main.py '
            f'--full_name "{full_name}" '
            f'--sha "{sha}" '
            f'--instance_id "{instance_id}" '
            f'--root_path "{root_path}" '
            f'--llm "{llm_model}"'
        )

        commands.append(cmd)

    return commands


def save_jsonl(data_list, output_file):
    """
    保存为 JSONL 格式

    Args:
        data_list: 数据列表
        output_file: 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        for data in data_list:
            json_line = json.dumps(data, ensure_ascii=False)
            f.write(json_line + '\n')

    print(f"✓ 已生成 JSONL 文件: {output_file} ({len(data_list)} 条数据)")


def save_commands(commands, output_file):
    """
    保存命令列表

    Args:
        commands: 命令列表
        output_file: 输出文件路径
    """
    with open(output_file, 'w', encoding='utf-8') as f:
        for cmd in commands:
            f.write(cmd + '\n')

    print(f"✓ 已生成命令文件: {output_file} ({len(commands)} 条命令)")


def main():
    parser = argparse.ArgumentParser(
        description='转换原始 benchmark 数据为 Repo2Run 所需格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本用法
  python prepare_benchmark.py \\
    --input dataset/benchmark_python_v3.0.jsonl \\
    --output_jsonl benchmark_python_3.0_repo2run.jsonl \\
    --output_commands commands.txt

  # 指定模型和路径
  python prepare_benchmark.py \\
    --input dataset/benchmark_python_v3.0.jsonl \\
    --output_jsonl benchmark_python_3.0_repo2run.jsonl \\
    --output_commands commands.txt \\
    --root_path /path/to/Repo2Run \\
    --llm gpt-4o-2024-05-13
        """
    )

    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='原始 benchmark JSONL 文件路径'
    )

    parser.add_argument(
        '--output_jsonl',
        type=str,
        default='benchmark_python_3.0_repo2run.jsonl',
        help='输出的完整 benchmark JSONL 文件路径（默认: benchmark_python_3.0_repo2run.jsonl）'
    )

    parser.add_argument(
        '--output_commands',
        type=str,
        default='commands.txt',
        help='输出的命令文件路径（默认: commands.txt）'
    )

    parser.add_argument(
        '--root_path',
        type=str,
        default=None,
        help='项目根路径（默认: 当前目录的绝对路径）'
    )

    parser.add_argument(
        '--llm',
        type=str,
        default='gpt-4o-2024-05-13',
        help='LLM 模型名称（默认: gpt-4o-2024-05-13）'
    )

    args = parser.parse_args()

    # 确定 root_path
    if args.root_path is None:
        root_path = os.path.abspath(os.path.dirname(__file__))
    else:
        root_path = os.path.abspath(args.root_path)

    print("=" * 80)
    print("Repo2Run 数据转换脚本")
    print("=" * 80)
    print(f"输入文件:      {args.input}")
    print(f"输出 JSONL:    {args.output_jsonl}")
    print(f"输出命令:      {args.output_commands}")
    print(f"项目根路径:    {root_path}")
    print(f"LLM 模型:      {args.llm}")
    print("=" * 80)
    print()

    # 1. 加载原始数据
    print(f"[1/4] 正在加载原始数据...")
    data_list = load_original_data(args.input)
    print(f"✓ 成功加载 {len(data_list)} 条数据")
    print()

    # 2. 转换数据
    print(f"[2/4] 正在转换数据格式...")
    transformed_list = transform_data(data_list, root_path, args.llm)
    print(f"✓ 成功转换 {len(transformed_list)} 条数据")
    print()

    # 3. 保存 JSONL 文件
    print(f"[3/4] 正在生成 JSONL 文件...")
    save_jsonl(transformed_list, args.output_jsonl)
    print()

    # 4. 生成并保存命令文件
    print(f"[4/4] 正在生成命令文件...")
    commands = generate_commands(transformed_list, root_path, args.llm)
    save_commands(commands, args.output_commands)
    print()

    print("=" * 80)
    print("✓ 数据转换完成！")
    print("=" * 80)
    print()
    print("接下来你可以:")
    print(f"  1. 执行 ./run.sh 来构建环境")
    print(f"  2. 执行 ./run_evaluation.sh 来评估结果")
    print()
    print("或者使用统一脚本:")
    print(f"  ./run_all.sh")
    print("=" * 80)


if __name__ == '__main__':
    main()
