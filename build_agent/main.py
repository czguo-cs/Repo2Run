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


import argparse
import json
import multiprocessing
import threading
import time
import os
import sys
from datetime import datetime, timedelta
from utils.sandbox import Sandbox
from agents.configuration import Configuration
import subprocess
from utils.waiting_list import WaitingList
from utils.conflict_list import ConflictList
from utils.integrate_dockerfile import integrate_dockerfile
import ast
import shutil

def move_files_to_repo(source_folder):
    # 定义目标文件夹所处的路径
    target_folder = os.path.join(source_folder, 'repo_inner_directory_long_long_name_to_avoid_duplicate')
    
    # 检查目标文件夹是否存在，不存在则创建
    if not os.path.exists(target_folder):
        os.mkdir(target_folder)
    
    # 遍历源文件夹中的所有文件和文件夹
    for item in os.listdir(source_folder):
        item_path = os.path.join(source_folder, item)
        
        # 跳过目标文件夹
        if item == 'repo_inner_directory_long_long_name_to_avoid_duplicate':
            continue
        
        # 移动文件或文件夹到目标文件夹
        shutil.move(item_path, os.path.join(target_folder, item))

    os.rename(target_folder, os.path.join(source_folder, 'repo'))

# 下载repo到utils/repo文件夹，并且去除最外层文件夹，去除可能存在的Dockerfile
def download_repo(root_path, full_name, sha, instance_id, output_dir):
    if len(full_name.split('/')) != 2:
        raise Exception("full_name Wrong!!!")
    author_name = full_name.split('/')[0]
    repo_name = full_name.split('/')[1]

    # Base repo path (shared across instances of the same repo)
    base_repo_path = f'{root_path}/utils/repo_base/{author_name}/{repo_name}'
    lock_file = f'{base_repo_path}.lock'

    # Instance-specific path
    target_path = f'{root_path}/utils/repo/{instance_id}'

    # Step 1: Ensure we have a base clone of the repo (shared, only clone once)
    if not os.path.exists(base_repo_path):
        print(f"Base repo not found. Cloning {full_name} to base directory...")
        os.makedirs(os.path.dirname(base_repo_path), exist_ok=True)

        # Use a lock file to prevent concurrent clones of the same repo
        import fcntl
        lock_fd = None
        try:
            # Create and acquire lock
            lock_fd = open(lock_file, 'w')
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)

            # Check again after acquiring lock (another process may have cloned it)
            if not os.path.exists(base_repo_path):
                # Clone to a temporary location first to avoid conflicts
                temp_base_path = f'{base_repo_path}_temp_clone'

                # Clean up any existing temp directory
                if os.path.exists(temp_base_path):
                    print(f"Cleaning up existing temp directory: {temp_base_path}")
                    try:
                        shutil.rmtree(temp_base_path)
                    except Exception as e:
                        print(f"Warning: Failed to remove temp directory: {e}")
                        # Try harder with system command
                        subprocess.run(f"rm -rf {temp_base_path}", shell=True)

                # Clone the repository
                download_cmd = f"git clone https://github.com/{full_name}.git {os.path.basename(temp_base_path)}"
                try:
                    subprocess.run(download_cmd, cwd=os.path.dirname(base_repo_path), check=True, shell=True, timeout=600)
                except subprocess.CalledProcessError as e:
                    print(f"Git clone failed: {e}")
                    # Clean up failed clone
                    if os.path.exists(temp_base_path):
                        shutil.rmtree(temp_base_path)
                    raise

                # Rename temp to final base path
                os.rename(temp_base_path, base_repo_path)
                print(f"✓ Base repo cloned to {base_repo_path}")
            else:
                print(f"✓ Base repo already exists (cloned by another process)")

        finally:
            # Release lock
            if lock_fd:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
                # Clean up lock file
                try:
                    os.remove(lock_file)
                except:
                    pass
    else:
        print(f"✓ Using existing base repo at {base_repo_path}")

    # Step 2: Clean up target directory if it exists
    if os.path.exists(target_path):
        print(f"Removing existing target directory: {target_path}")
        shutil.rmtree(target_path)

    # Step 3: Copy base repo to instance-specific directory
    print(f"Copying base repo to {target_path}...")
    shutil.copytree(base_repo_path, target_path, symlinks=True)

    # Step 4: Reset to specific commit
    print(f"Resetting to commit {sha[:8]}...")
    checkout_cmd = f"git reset --hard {sha}"
    result = subprocess.run(checkout_cmd, cwd=target_path, capture_output=True, shell=True)
    if result.returncode != 0:
        print(f"Warning: git reset failed: {result.stderr.decode('utf-8')}")
        # Fallback to git checkout
        checkout_cmd = f"git checkout {sha}"
        subprocess.run(checkout_cmd, cwd=target_path, capture_output=True, shell=True)

    # Step 5: Move files into 'repo' subdirectory (maintaining original structure)
    move_files_to_repo(target_path)

    if os.path.exists(f"{target_path}/repo/Dockerfile") and not os.path.isdir(f"{target_path}/repo/Dockerfile"):
        rm_dockerfile_cmd = f"rm -rf {target_path}/repo/Dockerfile"
        subprocess.run(rm_dockerfile_cmd, check=True, shell=True)

    # Run pipreqs to analyze dependencies
    pipreqs_cmd = "pipreqs --savepath=.pipreqs/requirements_pipreqs.txt --force"
    os.makedirs(f'{target_path}/repo/.pipreqs', exist_ok=True)
    try:
        pipreqs_warnings = subprocess.run(pipreqs_cmd, cwd=f"{target_path}/repo", check=True, shell=True, capture_output=True)
        with open(f'{target_path}/repo/.pipreqs/pipreqs_output.txt', 'w') as w1:
            w1.write(pipreqs_warnings.stdout.decode('utf-8'))
        with open(f'{target_path}/repo/.pipreqs/pipreqs_error.txt', 'w') as w2:
            w2.write(pipreqs_warnings.stderr.decode('utf-8'))
    except Exception as e:
        print(f"pipreqs failed: {e}")

    # Save SHA to output directory
    with open(f'{root_path}/output/{output_dir}/{instance_id}/sha.txt', 'w') as w1:
        w1.write(sha)

def main():
    # subprocess.run('docker rm -f $(docker ps -aq)', shell=True)
    parser = argparse.ArgumentParser(description='Run script with repository full name as an argument.')
    parser.add_argument('--full_name', type=str, help='The full name of the repository (e.g., user/repo).')
    parser.add_argument('--sha', type=str, help='sha')
    parser.add_argument('--instance_id', type=str, help='unique instance identifier')
    parser.add_argument('--root_path', type=str, help='root path')
    parser.add_argument('--llm', type=str, default='gpt-4o-2024-05-13', help='base LLM name')
    parser.add_argument('--output_dir', type=str, default='default', help='output directory name')

    args = parser.parse_args()

    waiting_list = WaitingList()
    conflict_list = ConflictList()

    root_path = args.root_path

    if not os.path.isabs(root_path):
        root_path = os.path.abspath(root_path)

    full_name = args.full_name
    sha = args.sha
    instance_id = args.instance_id
    llm = args.llm
    output_dir = args.output_dir
    print(full_name)
    # if os.path.exists(f'{root_path}/{full_name}/TIMEOUT'):
    #     sys.exit(123)
    print(sha)
    print(f"Instance ID: {instance_id}")
    print(f"Output directory: {output_dir}")
    if os.path.exists(f'{root_path}/output/{output_dir}/{instance_id}/patch'):
        rm_cmd = f"rm -rf {root_path}/output/{output_dir}/{instance_id}/patch"
        subprocess.run(rm_cmd, shell=True, check=True)
    if not os.path.exists(f'{root_path}/output/{output_dir}/{instance_id}'):
        subprocess.run(f'mkdir -p {root_path}/output/{output_dir}/{instance_id}', shell=True)
    if os.path.exists(f'{root_path}/utils/repo/{instance_id}'):
        init_cmd = f"rm -rf {root_path}/utils/repo/{instance_id} && mkdir -p {root_path}/utils/repo/{instance_id}"
    else:
        init_cmd = f"mkdir -p {root_path}/utils/repo/{instance_id}"
    subprocess.run(init_cmd, check=True, shell=True)

    def timer():
        time.sleep(3600*3)  # 等待3h (changed from 2h)
        print("Timeout for 3 hours!")
        os._exit(1)  # 强制退出程序

    # 启动定时器线程
    timer_thread = threading.Thread(target=timer)
    timer_thread.daemon = True
    timer_thread.start()

    # Record start time
    start_time = time.time()

    download_repo(root_path, full_name, sha, instance_id, output_dir)

    trajectory = []
    outer_commands = []  # Initialize to avoid NameError if exception occurs

    configuration_sandbox = Sandbox("python:3.10", full_name, root_path, instance_id, output_dir)
    configuration_sandbox.start_container()
    configuration_agent = Configuration(configuration_sandbox, 'python:3.10', full_name, root_path, llm, 50, instance_id, output_dir)

    try:
        msg, outer_commands = configuration_agent.run('/tmp', trajectory, waiting_list, conflict_list)

        # Record end time
        end_time = time.time()
        elapsed_seconds = end_time - start_time

        # Extract token statistics from trajectory
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        for item in msg:
            if isinstance(item, dict):
                if 'total_input_tokens' in item:
                    total_input_tokens += item['total_input_tokens']
                if 'total_output_tokens' in item:
                    total_output_tokens += item['total_output_tokens']
                if 'cost_tokens' in item:
                    total_tokens += item['cost_tokens']

        # Generate cost statistics
        cost_stats = {
            "elapsed_seconds": elapsed_seconds,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "model": llm
        }

        # Save trajectory
        with open(f'{root_path}/output/{output_dir}/{instance_id}/track.json', 'w') as w1:
            w1.write(json.dumps(msg, indent=4))

        # Save cost statistics
        with open(f'{root_path}/output/{output_dir}/{instance_id}/cost.json', 'w') as w_cost:
            w_cost.write(json.dumps(cost_stats, indent=4))

    except Exception as e:
        print(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()
        # Save error information
        end_time = time.time()
        elapsed_seconds = end_time - start_time
        error_info = {
            "error": str(e),
            "elapsed_seconds": elapsed_seconds
        }
        with open(f'{root_path}/output/{output_dir}/{instance_id}/error.json', 'w') as w_err:
            w_err.write(json.dumps(error_info, indent=4))

        # Try to extract token statistics from trajectory even on error
        total_input_tokens = 0
        total_output_tokens = 0
        total_tokens = 0

        try:
            for item in msg:
                if isinstance(item, dict):
                    if 'total_input_tokens' in item:
                        total_input_tokens += item['total_input_tokens']
                    if 'total_output_tokens' in item:
                        total_output_tokens += item['total_output_tokens']
                    if 'cost_tokens' in item:
                        total_tokens += item['cost_tokens']
        except:
            # If msg is not available or can't be processed, tokens will remain 0
            pass

        # Save cost statistics even on error
        cost_stats = {
            "elapsed_seconds": elapsed_seconds,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
            "model": llm,
            "status": "error",
            "error": str(e)
        }
        with open(f'{root_path}/output/{output_dir}/{instance_id}/cost.json', 'w') as w_cost:
            w_cost.write(json.dumps(cost_stats, indent=4))

        # Save trajectory if available
        try:
            if msg:
                with open(f'{root_path}/output/{output_dir}/{instance_id}/track.json', 'w') as w1:
                    w1.write(json.dumps(msg, indent=4))
        except:
            pass

        raise
    finally:
        # Always cleanup container and images, even on exception
        print("Cleaning up container and images...")
        commands = configuration_sandbox.stop_container()

    # Save commands (only if we got them)
    with open(f'{root_path}/output/{output_dir}/{instance_id}/inner_commands.json', 'w') as w2:
        w2.write(json.dumps(commands, indent=4))
    with open(f'{root_path}/output/{output_dir}/{instance_id}/outer_commands.json', 'w') as w3:
        w3.write(json.dumps(outer_commands, indent=4))
    try:
        integrate_dockerfile(f'{root_path}/output/{output_dir}/{instance_id}', full_name)
        msg = f'Generate success!'
        with open(f'{root_path}/output/{output_dir}/{instance_id}/track.txt', 'a') as a1:
            a1.write(msg + '\n')
    except Exception as e:
        msg = f'integrate_docker failed, reason:\n {e}'
        with open(f'{root_path}/output/{output_dir}/{instance_id}/track.txt', 'a') as a1:
            a1.write(msg + '\n')

    # Print cost summary
    print(f'\n{"="*60}')
    print(f'Cost Summary:')
    print(f'  Elapsed time: {elapsed_seconds:.2f} seconds')
    print(f'  Total tokens: {total_tokens}')
    print(f'  Input tokens: {total_input_tokens}')
    print(f'  Output tokens: {total_output_tokens}')
    print(f'  Model: {llm}')
    print(f'{"="*60}\n')

    # Clean up repos to save storage
    print("Cleaning up repositories...")

    # Extract repo names for cleanup
    author_name = full_name.split('/')[0]
    repo_name = full_name.split('/')[1]

    # Clean up instance-specific repo
    instance_repo_path = f'{root_path}/utils/repo/{instance_id}'
    if os.path.exists(instance_repo_path):
        try:
            shutil.rmtree(instance_repo_path)
            print(f"✓ Removed instance repo: {instance_repo_path}")
        except Exception as e:
            print(f"Warning: Failed to remove instance repo: {e}")

    # Note: We do NOT clean up base repo to avoid conflicts with concurrent tasks
    # Base repo is shared across multiple instances of the same repository
    # If you need to clean up base repos, do it manually after all tasks are completed:
    #   rm -rf {root_path}/utils/repo_base/
    print(f"ℹ Base repo kept for potential reuse: {root_path}/utils/repo_base/{author_name}/{repo_name}")

    print("✓ Cleanup completed!")

if __name__ == '__main__':
    # try:
    #     subprocess.run('docker rmi $(docker images --filter "dangling=true" -q) > /dev/null 2>&1', shell=True)
    # except:
    #     print("No dangling images")
    start_time = time.time()
    main()
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f'Spend totally {elapsed_time}.')