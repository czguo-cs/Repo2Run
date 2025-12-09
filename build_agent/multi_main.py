# Copyright (2025) Bytedance Ltd. and/or its affiliates 

# Licensed under the Apache License, Version 2.0 (the "License"); 
# you may not use this file except in compliance with the License. 
# You may obtain a copy of the License at 

#     https://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software 
# distributed under the License is distributed on an "AS IS" BASIS, 
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
# See the License for the specific language governing permissions and 
# limitations under the License. 


import multiprocessing
import subprocess
import os
import sys
import random
import time
import argparse

# 尝试导入 tqdm，如果失败则使用简单进度条
try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False


def run_command(command_and_output):
    command, output_dir = command_and_output

    # 如果命令中没有--output_dir参数，添加它
    if '--output_dir' not in command:
        command = command.rstrip() + f' --output_dir "{output_dir}"'

    # os.system('docker images --filter "dangling=true" --format "{{.ID}}" | xargs -r docker rmi')
    current_time = time.time()
    # 将时间戳转换为本地时间的 struct_time 对象
    local_time = time.localtime(current_time)

    # 将 struct_time 对象格式化为字符串
    formatted_time = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    # 提取 full_name, instance_id, root_path 和 output_dir
    full_name = command.split('--full_name "')[1].split('"')[0]
    instance_id = command.split('--instance_id "')[1].split('"')[0]
    root_path = command.split('--root_path "')[1].split('"')[0]

    # 提取 output_dir (应该已经在命令中了)
    try:
        cmd_output_dir = command.split('--output_dir "')[1].split('"')[0]
    except IndexError:
        cmd_output_dir = output_dir

    # 将日志文件保存到结果目录中，使用 instance_id 作为路径
    log_dir = os.path.join(root_path, 'output', cmd_output_dir, instance_id)
    os.makedirs(log_dir, exist_ok=True)  # 确保目录存在
    log_filepath = os.path.join(log_dir, 'run.log')

    # 打开日志文件
    with open(log_filepath, 'w') as log_file:
        def log(message):
            log_file.write(f'{message}\n')
            log_file.flush()

        log(f'Start time: {formatted_time}')
        log(f'Full name: {full_name}')
        log(f'Instance ID: {instance_id}')
        log(f'Command: {command}')
        log('='*80)

        vdb = subprocess.run("df -h | grep '/dev/vdb' | awk '{print $5}'", shell=True, capture_output=True, text=True)
        disk_usage = vdb.stdout.strip()
        if disk_usage and '%' in disk_usage:
            try:
                usage_percent = float(disk_usage.split('%')[0])
                if usage_percent > 90:
                    log('Warning! The disk /dev/vdb has occupied over 90% memories!')
                    sys.exit(1)
            except ValueError as e:
                log(f'Warning: Could not parse disk usage: {disk_usage}')
        else:
            log('Note: /dev/vdb disk not found, skipping disk check')

        try:
            log(f'Begin: {command}')
            # 将 subprocess 的输出重定向到日志文件
            result = subprocess.run(command, shell=True, stdout=log_file, stderr=log_file)
            log(f'Finish: {command}')
            log(f'Return code: {result.returncode}')

            # 清理 Docker 容器，使用 instance_id
            image_name = instance_id.lower().replace('/', '_').replace('-', '_')
            finish_command.append(image_name)
            for fc in finish_command:
                try:
                    rm_cmd = f'docker ps -a --filter ancestor={fc}:tmp -q | xargs -r docker rm'
                    subprocess.run(rm_cmd, shell=True, capture_output=True, text=True)
                except:
                    pass
        except Exception as e:
            log(f"Error: {command}, {e}")
            return {'full_name': full_name, 'instance_id': instance_id, 'status': 'error', 'log_file': log_filepath, 'time': formatted_time}

    # 返回任务完成信息
    return {'full_name': full_name, 'instance_id': instance_id, 'status': 'completed', 'log_file': log_filepath, 'time': formatted_time}

if __name__ == '__main__':
    # Clean up Docker containers, ignore error if no containers exist
    os.system('docker rm -f $(docker ps -aq) 2>/dev/null || true')

    # 解析命令行参数
    parser = argparse.ArgumentParser(description='Run multiple build tasks in parallel.')
    parser.add_argument('script_path', type=str, help='Path to the file containing commands to execute')
    parser.add_argument('--output_dir', type=str, default='default', help='Output directory name for all tasks (default: "default")')
    args = parser.parse_args()

    script_path = args.script_path
    output_dir = args.output_dir

    print(f'Output directory: {output_dir}')
    print('='*80)

    # 要执行的命令列表
    try:
        with open(script_path, 'r') as r1:
            commands = r1.readlines()
    except:
        print(f'Error: {script_path}')
        sys.exit(1)

    finish_command = list()
    random.shuffle(commands)

    # 将output_dir与每个命令配对
    commands_with_output = [(cmd.strip(), output_dir) for cmd in commands if cmd.strip()]

    print(f'Total commands: {len(commands_with_output)}')
    print(f'Max concurrent processes: 5')
    print('='*80)

    # 创建进程池，最多同时运行5个进程
    completed = 0
    errors = 0

    with multiprocessing.Pool(processes=5) as pool:
        # 使用 imap_unordered 来逐个处理结果，以便更新进度条
        if TQDM_AVAILABLE:
            # 使用 tqdm 进度条
            with tqdm(total=len(commands_with_output), desc="Processing tasks", unit="task") as pbar:
                for result in pool.imap_unordered(run_command, commands_with_output):
                    completed += 1
                    if result['status'] == 'error':
                        errors += 1
                        pbar.set_postfix({'completed': completed, 'errors': errors})
                    else:
                        pbar.set_postfix({'completed': completed, 'errors': errors})
                    pbar.update(1)
        else:
            # 使用简单的文本进度条
            print(f"\nProgress: [{'.'*50}] 0/{len(commands_with_output)}", end='', flush=True)
            for result in pool.imap_unordered(run_command, commands_with_output):
                completed += 1
                if result['status'] == 'error':
                    errors += 1
                # 计算进度百分比
                progress = int((completed / len(commands_with_output)) * 50)
                print(f"\rProgress: [{'='*progress}{'.'*(50-progress)}] {completed}/{len(commands_with_output)} (Errors: {errors})", end='', flush=True)
            print()  # 换行

    print('='*80)
    print(f'All tasks completed!')
    print(f'Total: {len(commands_with_output)}, Completed: {completed}, Errors: {errors}')
    print(f'Logs saved in output/{output_dir}/{{instance_id}}/run.log')