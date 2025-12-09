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


import os
import sys
from openai import OpenAI
import time

# Initialize OpenAI client with environment variables
def get_openai_client():
    api_key = os.getenv("OPENAI_KEY")
    if not api_key:
        print("Error: OPENAI_KEY environment variable is not set")
        sys.exit(1)

    base_url = os.getenv("OPENAI_API_BASE_URL", None)

    return OpenAI(api_key=api_key, base_url=base_url, timeout=300)

# Global client instance
_client = None

def get_llm_response(model: str, messages, temperature = 0.0, n = 1, max_tokens = 4096):
    global _client
    if _client is None:
        _client = get_openai_client()

    max_retry = 5
    count = 0
    while count < max_retry:
        try:
            response = _client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                n=n,
                max_tokens=max_tokens
            )
            # Convert usage object to dict
            usage_dict = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            # Return all choices as a list (to support n > 1)
            choices_content = [choice.message.content for choice in response.choices]
            return choices_content, usage_dict
        except Exception as e:
            print(f"Error: {e}")
            count += 1
            time.sleep(3)
    return None, None