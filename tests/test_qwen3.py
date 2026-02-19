#!/usr/bin/env python3
"""简单的 Qwen3 模型调用测试脚本

用法示例�?
  API_KEY=xxx python test_qwen3.py
或指定参数：
  python test_qwen3.py --url http://10.104.6.197:38099/v1 --model Qwen3-32B --prompt "你好"
"""
import os
import sys
import argparse
import json

try:
    import requests
except Exception:
    requests = None


def call_model(base_url, model, prompt, api_key=None, timeout=30):
    # 尝试 OpenAI 兼容�?Chat Completions 路径
    endpoint = base_url.rstrip('/') + '/chat/completions'
    payload = {
        'model': model,
        'messages': [
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.0,
    }

    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = f'Bearer {api_key}'

    if requests:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        try:
            data = resp.json()
        except Exception:
            resp.raise_for_status()
            raise
        return resp.status_code, data

    # 如果没有 requests，降级到 urllib
    import urllib.request
    req = urllib.request.Request(endpoint, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as f:
        body = f.read().decode('utf-8')
        return f.getcode(), json.loads(body)


def extract_text(response_json):
    # 支持常见的返回结�?
    if not isinstance(response_json, dict):
        return None
    choices = response_json.get('choices') or []
    if choices:
        first = choices[0]
        # chat completions 格式
        if isinstance(first.get('message'), dict) and 'content' in first['message']:
            return first['message']['content']
        # streaming/delta 格式
        if isinstance(first.get('delta'), dict) and 'content' in first['delta']:
            return first['delta']['content']
        # text/completion 格式
        if 'text' in first:
            return first['text']
    # 兼容一些厂商直接把回复放在 data �?result
    for k in ('result', 'data', 'output'):
        v = response_json.get(k)
        if isinstance(v, str):
            return v
    return None


def main():
    parser = argparse.ArgumentParser(description='Simple test for Qwen3 model endpoint')
    parser.add_argument('--url', default=os.environ.get('MODEL_URL', 'http://10.104.6.16:38099/v1'), help='Base URL of the model server')
    parser.add_argument('--model', default=os.environ.get('MODEL_NAME', 'Qwen3-32B'), help='Model name')
    parser.add_argument('--prompt', default='请用一句话简单自我介绍�?, help='Prompt to send to the model')
    parser.add_argument('--api-key', default=os.environ.get('API_KEY'), help='Optional API key (or set API_KEY env)')
    args = parser.parse_args()

    if requests is None:
        print('warning: `requests` module not available, using urllib (推荐安装 requests)')

    print(f'调用地址: {args.url}  模型: {args.model}')
    try:
        status, data = call_model(args.url, args.model, args.prompt, api_key=args.api_key)
    except Exception as e:
        print('请求失败�?, e)
        sys.exit(2)

    print('\nHTTP 状�?', status)
    print('\n完整返回 JSON:')
    print(json.dumps(data, ensure_ascii=False, indent=2))

    text = extract_text(data)
    if text:
        print('\n解析到的回复�?)
        print(text)
    else:
        print('\n未能从返回中解析到文本回复，请查看完�?JSON�?)


if __name__ == '__main__':
    main()
