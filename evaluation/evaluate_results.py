#!/usr/bin/env python3
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

"""
Evaluate benchmark results by building Dockerfiles and running tests.
Supports parallel processing for efficiency.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import multiprocessing


def load_benchmark_data(benchmark_file: str) -> Dict[str, dict]:
    """
    Load benchmark data and create a mapping from instance_id to data.

    Args:
        benchmark_file: Path to benchmark JSONL file

    Returns:
        Dictionary mapping instance_id to benchmark data
    """
    data_map = {}
    with open(benchmark_file, 'r') as f:
        for line in f:
            if line.strip():
                data = json.loads(line.strip())
                instance_id = data.get('instance_id')
                if instance_id:
                    data_map[instance_id] = data
    return data_map


def find_all_instances(output_dir: str) -> List[Tuple[str, bool, bool]]:
    """
    Find all instances in the output directory and check for Dockerfile existence.

    Args:
        output_dir: Output directory containing instance subdirectories

    Returns:
        List of tuples (instance_id, has_folder, has_dockerfile)
    """
    instances = []

    if not os.path.exists(output_dir):
        print(f"Warning: Output directory does not exist: {output_dir}")
        return instances

    for item in sorted(os.listdir(output_dir)):
        item_path = os.path.join(output_dir, item)
        if os.path.isdir(item_path):
            dockerfile_path = os.path.join(item_path, 'Dockerfile')
            has_dockerfile = os.path.exists(dockerfile_path)
            instances.append((item, True, has_dockerfile))

    return instances


def extract_test_files_from_patch(test_patch: str) -> List[str]:
    """
    Extract test file paths from test_patch.

    Args:
        test_patch: The test patch content in git diff format

    Returns:
        List of test file paths
    """
    test_files = []
    if not test_patch:
        return test_files

    lines = test_patch.split('\n')
    for line in lines:
        # Look for lines like "diff --git a/path/to/test.py b/path/to/test.py"
        if line.startswith('diff --git'):
            parts = line.split()
            if len(parts) >= 3:
                file_path = parts[2][2:]  # Remove 'a/' prefix
                # Only include test files
                if 'test' in file_path.lower() and file_path.endswith('.py'):
                    test_files.append(file_path)

    return test_files


def extract_test_command_from_dockerfile(dockerfile_path: str) -> Optional[str]:
    """
    Extract the test command from Dockerfile (usually the CMD or last RUN with pytest).

    Args:
        dockerfile_path: Path to the Dockerfile

    Returns:
        Test command string or None
    """
    try:
        with open(dockerfile_path, 'r') as f:
            lines = f.readlines()

        # Look for CMD instruction or pytest commands
        for line in reversed(lines):
            line = line.strip()
            if line.startswith('CMD'):
                # Extract command from CMD instruction
                cmd = line[3:].strip()
                if cmd.startswith('['):
                    # JSON array format
                    import ast
                    return ' '.join(ast.literal_eval(cmd))
                else:
                    # Shell format
                    return cmd.strip('"\'')

        # Default to pytest if no CMD found
        return 'cd /repo && pytest -xvs'
    except Exception as e:
        print(f"Warning: Could not extract test command from {dockerfile_path}: {e}")
        return 'cd /repo && pytest -xvs'


def prepare_build_context(dockerfile_path: str, instance_dir: str, root_path: str) -> None:
    """
    Prepare build context by copying required files to instance directory.

    Args:
        dockerfile_path: Path to the Dockerfile
        instance_dir: Instance directory (build context)
        root_path: Root directory of the project
    """
    try:
        with open(dockerfile_path, 'r') as f:
            dockerfile_content = f.read()

        # Fix old bug: replace "COPY search_patch" with "COPY patch"
        if 'COPY search_patch' in dockerfile_content:
            dockerfile_content = dockerfile_content.replace('COPY search_patch /search_patch', 'COPY patch /patch')
            with open(dockerfile_path, 'w') as f:
                f.write(dockerfile_content)

        # Find all COPY instructions
        copy_pattern = r'^COPY\s+(\S+)\s+'
        for line in dockerfile_content.split('\n'):
            match = re.match(copy_pattern, line)
            if match:
                source_file = match.group(1)

                # Check if file exists in instance_dir
                dest_path = os.path.join(instance_dir, source_file)
                if os.path.exists(dest_path):
                    continue

                # Try to find file in project directory
                possible_paths = [
                    os.path.join(root_path, source_file),
                    os.path.join(root_path, 'build_agent', 'tools', source_file),
                ]

                for src_path in possible_paths:
                    if os.path.exists(src_path):
                        shutil.copy2(src_path, dest_path)
                        break
    except Exception as e:
        # Non-critical, just log warning
        pass


def evaluate_single_instance(
    instance_id: str,
    output_dir: str,
    benchmark_data: Dict[str, dict],
    timeout: int = 600,
    root_path: str = None
) -> Dict:
    """
    Evaluate a single instance by building Dockerfile and running tests.

    New evaluation mechanism:
    1. Build Docker image from Dockerfile
    2. Stage 1: Apply only test_patch, run tests (expected to fail)
    3. Stage 2: Apply test_patch + fix_patch, run tests (expected to pass)
    4. Success criteria:
       - test_only_stage fails AND both_patches_stage passes => f2p verification success
       - both_patches_stage passes => environment setup success

    Args:
        instance_id: Instance identifier
        output_dir: Output directory path
        benchmark_data: Benchmark data mapping
        timeout: Timeout in seconds for Docker operations
        root_path: Root path of the project (for finding build context files)

    Returns:
        Result dictionary with evaluation status
    """
    result = {
        'instance_id': instance_id,
        'status': 'unknown',
        'success': False,
        'f2p_success': False,
        'message': '',
        'build_time': 0,
        'test_only_time': 0,
        'both_patches_time': 0,
        'test_only_status': 'unknown',
        'both_patches_status': 'unknown',
        'timestamp': datetime.now().isoformat()
    }

    instance_dir = os.path.join(output_dir, instance_id)
    dockerfile_path = os.path.join(instance_dir, 'Dockerfile')

    # Check if instance folder exists
    if not os.path.exists(instance_dir):
        result['status'] = 'no_folder'
        result['message'] = 'Instance folder does not exist'
        return result

    # Check if Dockerfile exists
    if not os.path.exists(dockerfile_path):
        result['status'] = 'no_dockerfile'
        result['message'] = 'Dockerfile not found'
        return result

    # Check if instance exists in benchmark
    if instance_id not in benchmark_data:
        result['status'] = 'not_in_benchmark'
        result['message'] = 'Instance not found in benchmark data'
        return result

    image_tag = f"eval_test:{instance_id.replace('/', '_').replace('__', '_')}"
    container_name = f"eval_test_{instance_id.replace('/', '_').replace('__', '_')}"

    # Create logs directory if it doesn't exist
    logs_dir = os.path.join(instance_dir, 'evaluation_logs')
    os.makedirs(logs_dir, exist_ok=True)

    # Prepare build context (copy required files)
    if root_path:
        prepare_build_context(dockerfile_path, instance_dir, root_path)

    # Ensure code_edit.py exists in instance_dir
    code_edit_src = os.path.join(root_path, 'build_agent', 'tools', 'code_edit.py')
    code_edit_dst = os.path.join(instance_dir, 'code_edit.py')
    if os.path.exists(code_edit_src) and not os.path.exists(code_edit_dst):
        shutil.copy2(code_edit_src, code_edit_dst)

    try:
        # Build Docker image
        build_start = time.time()
        build_cmd = f"docker build -t {image_tag} -f {dockerfile_path} {instance_dir}"

        # Open log file for real-time writing
        build_log_path = os.path.join(logs_dir, 'build.log')
        with open(build_log_path, 'w') as log_file:
            log_file.write("=== Build Command ===\n")
            log_file.write(f"{build_cmd}\n\n")
            log_file.write("=== Build Output ===\n")
            log_file.flush()

            # Run build with real-time output
            process = subprocess.Popen(
                build_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Read and write output line by line
            build_output = []
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()
                build_output.append(line)

            return_code = process.wait(timeout=timeout)

            log_file.write(f"\n\n=== Return Code ===\n")
            log_file.write(f"{return_code}\n")

        result['build_time'] = time.time() - build_start

        # Write build time
        with open(build_log_path, 'a') as log_file:
            log_file.write(f"\n=== Build Time ===\n")
            log_file.write(f"{result['build_time']:.2f} seconds\n")

        if return_code != 0:
            result['status'] = 'build_failed'
            result['message'] = f"Docker build failed (see {build_log_path})"
            result['build_log'] = build_log_path
            return result

        # Extract test files and patches from benchmark data
        benchmark_entry = benchmark_data.get(instance_id, {})
        test_patch = benchmark_entry.get('test_patch', '')
        fix_patch = benchmark_entry.get('patch', '')

        test_files = []
        if test_patch:
            test_files = extract_test_files_from_patch(test_patch)

        if not test_files:
            result['status'] = 'no_test_files'
            result['message'] = 'No test files found in test_patch'
            return result

        # Write patches to temporary files in instance_dir
        test_patch_file = os.path.join(instance_dir, 'test.patch')
        fix_patch_file = os.path.join(instance_dir, 'fix.patch')

        with open(test_patch_file, 'w') as f:
            f.write(test_patch)

        with open(fix_patch_file, 'w') as f:
            f.write(fix_patch)

        # Build test command
        test_files_str = ' '.join(test_files)
        test_cmd_base = f'cd /repo && pytest -rA {test_files_str} -v'

        # ========================================
        # Stage 1: Test with only test_patch
        # ========================================
        test_only_log_path = os.path.join(logs_dir, 'test_only.log')

        # Clean up any existing container
        subprocess.run(
            f"docker rm -f {container_name} 2>/dev/null || true",
            shell=True,
            capture_output=True
        )

        test_only_start = time.time()

        # Use docker run with volume mount to apply test patch and run tests
        test_only_cmd = f"docker run --name {container_name} -v {test_patch_file}:/test.patch {image_tag} bash -c 'cd /repo && git apply /test.patch && {test_cmd_base}'"

        with open(test_only_log_path, 'w') as log_file:
            log_file.write("=== Stage 1: Test with only test_patch ===\n\n")
            log_file.write("=== Test Files ===\n")
            for tf in test_files:
                log_file.write(f"  - {tf}\n")
            log_file.write("\n=== Applying test_patch only ===\n")
            log_file.write("=== Test Command ===\n")
            log_file.write(f"{test_cmd_base}\n\n")
            log_file.write("=== Test Output ===\n")
            log_file.flush()

            # Run test with real-time output
            process = subprocess.Popen(
                test_only_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Read and write output line by line
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()

            test_only_return_code = process.wait(timeout=timeout)

            log_file.write(f"\n\n=== Return Code ===\n")
            log_file.write(f"{test_only_return_code}\n")

        result['test_only_time'] = time.time() - test_only_start
        result['test_only_status'] = 'passed' if test_only_return_code == 0 else 'failed'

        # Write test time
        with open(test_only_log_path, 'a') as log_file:
            log_file.write(f"\n=== Test Time ===\n")
            log_file.write(f"{result['test_only_time']:.2f} seconds\n")

        # ========================================
        # Stage 2: Test with both test_patch and fix_patch
        # ========================================
        both_patches_log_path = os.path.join(logs_dir, 'both_patches.log')

        # Clean up container from stage 1
        subprocess.run(
            f"docker rm -f {container_name} 2>/dev/null || true",
            shell=True,
            capture_output=True
        )

        both_patches_start = time.time()
        # Apply both patches and run tests using volume mount
        both_patches_cmd = (
            f"docker run --name {container_name} "
            f"-v {fix_patch_file}:/fix.patch "
            f"-v {test_patch_file}:/test.patch "
            f"{image_tag} bash -c '"
            f"cd /repo && git apply /fix.patch && git apply /test.patch && {test_cmd_base}'"
        )

        with open(both_patches_log_path, 'w') as log_file:
            log_file.write("=== Stage 2: Test with both fix_patch and test_patch ===\n\n")
            log_file.write("=== Test Files ===\n")
            for tf in test_files:
                log_file.write(f"  - {tf}\n")
            log_file.write("\n=== Applying fix_patch + test_patch ===\n")
            log_file.write("=== Test Command ===\n")
            log_file.write(f"{test_cmd_base}\n\n")
            log_file.write("=== Test Output ===\n")
            log_file.flush()

            # Run test with real-time output
            process = subprocess.Popen(
                both_patches_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            # Read and write output line by line
            for line in process.stdout:
                log_file.write(line)
                log_file.flush()

            both_patches_return_code = process.wait(timeout=timeout)

            log_file.write(f"\n\n=== Return Code ===\n")
            log_file.write(f"{both_patches_return_code}\n")

        result['both_patches_time'] = time.time() - both_patches_start
        result['both_patches_status'] = 'passed' if both_patches_return_code == 0 else 'failed'

        # Write test time
        with open(both_patches_log_path, 'a') as log_file:
            log_file.write(f"\n=== Test Time ===\n")
            log_file.write(f"{result['both_patches_time']:.2f} seconds\n")

        # ========================================
        # Determine final result
        # ========================================
        result['test_only_log'] = test_only_log_path
        result['both_patches_log'] = both_patches_log_path

        # Success if both_patches_stage passes
        if both_patches_return_code == 0:
            result['success'] = True

            # F2P success if test_only fails but both_patches passes
            if test_only_return_code != 0:
                result['f2p_success'] = True
                result['status'] = 'f2p_passed'
                result['message'] = 'F2P verification passed: test_only failed, both_patches passed'
            else:
                result['f2p_success'] = False
                result['status'] = 'env_passed'
                result['message'] = 'Environment setup passed: both stages passed (test_only should have failed)'
        else:
            result['success'] = False
            result['f2p_success'] = False
            result['status'] = 'test_failed'
            result['message'] = f'Both patches stage failed with return code {both_patches_return_code}'

    except subprocess.TimeoutExpired:
        result['status'] = 'timeout'
        result['message'] = f'Operation timed out after {timeout} seconds'

        # Save timeout log
        timeout_log_path = os.path.join(logs_dir, 'timeout.log')
        with open(timeout_log_path, 'w') as f:
            f.write(f"=== Timeout occurred after {timeout} seconds ===\n")
            f.write(f"Instance: {instance_id}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        result['timeout_log'] = timeout_log_path

        # Try to kill container
        subprocess.run(
            f"docker kill {container_name} 2>/dev/null || true",
            shell=True,
            capture_output=True
        )
    except Exception as e:
        result['status'] = 'error'
        result['message'] = f'Unexpected error: {str(e)}'

        # Save error log
        error_log_path = os.path.join(logs_dir, 'error.log')
        with open(error_log_path, 'w') as f:
            f.write(f"=== Unexpected Error ===\n")
            f.write(f"Error: {str(e)}\n")
            f.write(f"Instance: {instance_id}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
        result['error_log'] = error_log_path
    finally:
        # Cleanup
        subprocess.run(
            f"docker rm -f {container_name} 2>/dev/null || true",
            shell=True,
            capture_output=True
        )
        subprocess.run(
            f"docker rmi {image_tag} 2>/dev/null || true",
            shell=True,
            capture_output=True
        )

    return result


def evaluate_instance_wrapper(args):
    """Wrapper for parallel execution."""
    return evaluate_single_instance(*args)


def main():
    parser = argparse.ArgumentParser(
        description='Evaluate benchmark results by building Dockerfiles and running tests'
    )
    parser.add_argument(
        '--output_dir',
        type=str,
        required=True,
        help='Output directory containing instance subdirectories (e.g., /output/benchmark_python_3.0_repo2run)'
    )
    parser.add_argument(
        '--benchmark_file',
        type=str,
        required=True,
        help='Path to benchmark JSONL file'
    )
    parser.add_argument(
        '--instances',
        type=str,
        nargs='*',
        help='Specific instance IDs to evaluate (if not provided, evaluate all)'
    )
    parser.add_argument(
        '--parallel',
        type=int,
        default=1,
        help='Number of parallel workers (default: 1 for sequential)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=600,
        help='Timeout in seconds for each instance (default: 600)'
    )
    parser.add_argument(
        '--max_instances',
        type=int,
        default=None,
        help='Maximum number of instances to evaluate'
    )

    args = parser.parse_args()

    # Normalize paths
    output_dir = os.path.abspath(args.output_dir)
    benchmark_file = os.path.abspath(args.benchmark_file)

    if not os.path.exists(output_dir):
        print(f"Error: Output directory does not exist: {output_dir}")
        sys.exit(1)

    if not os.path.exists(benchmark_file):
        print(f"Error: Benchmark file does not exist: {benchmark_file}")
        sys.exit(1)

    print(f"{'='*80}")
    print(f"Benchmark Results Evaluation")
    print(f"{'='*80}")
    print(f"Output directory: {output_dir}")
    print(f"Benchmark file: {benchmark_file}")
    print(f"Parallel workers: {args.parallel}")
    print(f"Timeout: {args.timeout}s")
    print()

    # Load benchmark data
    print("Loading benchmark data...")
    benchmark_data = load_benchmark_data(benchmark_file)
    print(f"Loaded {len(benchmark_data)} instances from benchmark")
    print()

    # Find instances to evaluate
    if args.instances:
        instances_to_eval = args.instances
        print(f"Evaluating {len(instances_to_eval)} specified instance(s)")
    else:
        all_instances = find_all_instances(output_dir)
        instances_to_eval = [inst_id for inst_id, has_folder, has_dockerfile in all_instances]
        print(f"Found {len(instances_to_eval)} instance(s) in output directory")

        # Report summary of what was found
        no_dockerfile = sum(1 for _, has_folder, has_dockerfile in all_instances if has_folder and not has_dockerfile)
        if no_dockerfile > 0:
            print(f"  - {no_dockerfile} instance(s) without Dockerfile (will be marked as failed)")

    if args.max_instances:
        instances_to_eval = instances_to_eval[:args.max_instances]
        print(f"Limiting to first {args.max_instances} instance(s)")

    print()

    # Initialize results tracking
    results = {
        'total': len(instances_to_eval),
        'passed': 0,
        'failed': 0,
        'f2p_passed': 0,
        'env_passed': 0,
        'no_dockerfile': 0,
        'no_folder': 0,
        'no_test_files': 0,
        'build_failed': 0,
        'test_failed': 0,
        'timeout': 0,
        'error': 0,
        'details': []
    }

    start_time = time.time()

    # Calculate root_path from output_dir
    # output_dir is like: /path/to/Repo2Run/output/benchmark_python_3.0_repo2run
    # root_path should be: /path/to/Repo2Run
    root_path = os.path.dirname(os.path.dirname(output_dir))

    # Prepare arguments for parallel execution
    eval_args = [
        (inst_id, output_dir, benchmark_data, args.timeout, root_path)
        for inst_id in instances_to_eval
    ]

    # Evaluate instances
    if args.parallel > 1:
        # Parallel execution
        print(f"Starting parallel evaluation with {args.parallel} workers...")
        print()

        with ProcessPoolExecutor(max_workers=args.parallel) as executor:
            futures = {
                executor.submit(evaluate_instance_wrapper, arg): arg[0]
                for arg in eval_args
            }

            completed = 0
            for future in as_completed(futures):
                instance_id = futures[future]
                completed += 1

                try:
                    result = future.result()
                    results['details'].append(result)

                    # Update counts
                    if result['success']:
                        results['passed'] += 1
                        status_symbol = '✓'

                        # Track f2p_passed vs env_passed
                        if result['f2p_success']:
                            results['f2p_passed'] += 1
                        else:
                            results['env_passed'] += 1
                    else:
                        results['failed'] += 1
                        status_symbol = '✗'

                        # Update specific failure counts
                        status = result['status']
                        if status == 'no_dockerfile':
                            results['no_dockerfile'] += 1
                        elif status == 'no_folder':
                            results['no_folder'] += 1
                        elif status == 'no_test_files':
                            results['no_test_files'] += 1
                        elif status == 'build_failed':
                            results['build_failed'] += 1
                        elif status == 'test_failed':
                            results['test_failed'] += 1
                        elif status == 'timeout':
                            results['timeout'] += 1
                        elif status == 'error':
                            results['error'] += 1

                    # Print progress
                    print(f"[{completed}/{len(instances_to_eval)}] {status_symbol} {instance_id}: {result['status']}")

                except Exception as e:
                    print(f"[{completed}/{len(instances_to_eval)}] ✗ {instance_id}: Exception - {str(e)}")
                    results['failed'] += 1
                    results['error'] += 1
                    results['details'].append({
                        'instance_id': instance_id,
                        'status': 'error',
                        'success': False,
                        'message': str(e)
                    })
    else:
        # Sequential execution
        print("Starting sequential evaluation...")
        print()

        for idx, (inst_id, output_dir, benchmark_data, timeout, root_path) in enumerate(eval_args, 1):
            print(f"[{idx}/{len(instances_to_eval)}] Evaluating: {inst_id}")

            result = evaluate_single_instance(inst_id, output_dir, benchmark_data, timeout, root_path)
            results['details'].append(result)

            # Update counts
            if result['success']:
                results['passed'] += 1
                print(f"  ✓ {result['status']}: {result['message']}")

                # Track f2p_passed vs env_passed
                if result['f2p_success']:
                    results['f2p_passed'] += 1
                else:
                    results['env_passed'] += 1
            else:
                results['failed'] += 1
                print(f"  ✗ {result['status']}: {result['message']}")

                # Update specific failure counts
                status = result['status']
                if status == 'no_dockerfile':
                    results['no_dockerfile'] += 1
                elif status == 'no_folder':
                    results['no_folder'] += 1
                elif status == 'no_test_files':
                    results['no_test_files'] += 1
                elif status == 'build_failed':
                    results['build_failed'] += 1
                elif status == 'test_failed':
                    results['test_failed'] += 1
                elif status == 'timeout':
                    results['timeout'] += 1
                elif status == 'error':
                    results['error'] += 1

            print()

    elapsed_time = time.time() - start_time

    # Save detailed results
    output_dir_name = os.path.basename(output_dir.rstrip('/'))
    result_file = os.path.join(os.path.dirname(output_dir), f'evaluation_results_{output_dir_name}.json')

    summary = {
        'timestamp': datetime.now().isoformat(),
        'output_dir': output_dir,
        'benchmark_file': benchmark_file,
        'elapsed_seconds': elapsed_time,
        'statistics': {
            'total': results['total'],
            'passed': results['passed'],
            'failed': results['failed'],
            'pass_rate': f"{results['passed'] / results['total'] * 100:.2f}%" if results['total'] > 0 else "0%",
            'success_breakdown': {
                'f2p_passed': results['f2p_passed'],
                'env_passed': results['env_passed']
            },
            'failure_breakdown': {
                'no_dockerfile': results['no_dockerfile'],
                'no_folder': results['no_folder'],
                'no_test_files': results['no_test_files'],
                'build_failed': results['build_failed'],
                'test_failed': results['test_failed'],
                'timeout': results['timeout'],
                'error': results['error']
            }
        },
        'details': results['details']
    }

    with open(result_file, 'w') as f:
        json.dump(summary, f, indent=2)

    # Print summary
    print()
    print(f"{'='*80}")
    print("EVALUATION SUMMARY")
    print(f"{'='*80}")
    print(f"Total instances:     {results['total']}")
    print(f"Passed:              {results['passed']} ({results['passed'] / results['total'] * 100:.1f}%)" if results['total'] > 0 else "Passed: 0")
    print(f"  - F2P Passed:      {results['f2p_passed']} ({results['f2p_passed'] / results['total'] * 100:.1f}%)" if results['total'] > 0 else "  - F2P Passed: 0")
    print(f"  - Env Passed:      {results['env_passed']} ({results['env_passed'] / results['total'] * 100:.1f}%)" if results['total'] > 0 else "  - Env Passed: 0")
    print(f"Failed:              {results['failed']} ({results['failed'] / results['total'] * 100:.1f}%)" if results['total'] > 0 else "Failed: 0")
    print()
    print("Failure breakdown:")
    print(f"  - No Dockerfile:   {results['no_dockerfile']}")
    print(f"  - No Folder:       {results['no_folder']}")
    print(f"  - No Test Files:   {results['no_test_files']}")
    print(f"  - Build Failed:    {results['build_failed']}")
    print(f"  - Test Failed:     {results['test_failed']}")
    print(f"  - Timeout:         {results['timeout']}")
    print(f"  - Other Error:     {results['error']}")
    print()
    print(f"Elapsed time:        {elapsed_time:.2f} seconds")
    print(f"Average per instance: {elapsed_time / results['total']:.2f} seconds" if results['total'] > 0 else "Average: N/A")
    print()
    print(f"Detailed results saved to: {result_file}")
    print(f"{'='*80}")

    # Exit with appropriate code
    sys.exit(0 if results['failed'] == 0 else 1)


if __name__ == '__main__':
    main()
