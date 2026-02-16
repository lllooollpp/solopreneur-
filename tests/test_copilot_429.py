#!/usr/bin/env python3
"""
最小化测试脚本 - 诊断 GitHub Copilot 429 错误
"""
import asyncio
import httpx
import json
from pathlib import Path

# Pool 目录
POOL_DIR = Path.home() / ".solopreneur" / "pool"

# GitHub Copilot API 端点
COPILOT_CHAT_URL = "https://api.githubcopilot.com/chat/completions"
COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"

async def test_slot(slot_id: int):
    """测试单个 slot �?Copilot API"""
    slot_file = POOL_DIR / f"slot_{slot_id}.json"

    if not slot_file.exists():
        print(f"�?Slot {slot_id} 不存�?)
        return

    # 读取 slot 配置
    with open(slot_file, 'r') as f:
        slot_data = json.load(f)

    copilot_token = slot_data.get('copilot_token')
    label = slot_data.get('label', f'Slot{slot_id}')

    print(f"\n{'='*60}")
    print(f"测试 Slot {slot_id} ({label})")
    print(f"{'='*60}")
    print(f"📌 Copilot Token: {copilot_token[:50]}...")
    print(f"📌 Token 过期时间: {slot_data.get('expires_at')}")
    print(f"📌 历史请求: {slot_data.get('total_requests')}")
    print(f"📌 历史 429: {slot_data.get('total_429s')}")

    # 构建 HTTP 客户�?    headers = {
        "Authorization": f"Bearer {copilot_token}",
        "Content-Type": "application/json",
        "User-Agent": "GithubCopilot/1.254.0",
        "Editor-Version": "vscode/1.96.0",
        "Editor-Plugin-Version": "copilot-chat/1.254.0",
        "Openai-Organization": "github-copilot",
        "Copilot-Integration-Id": "vscode-chat",
    }

    # 模拟真实�?tools 定义（类�?subagent.py 中的�?    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取文件内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "写入文件内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "content": {"type": "string", "description": "文件内容"}
                    },
                    "required": ["path", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_dir",
                "description": "列出目录内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "目录路径"}
                    },
                    "required": ["path"]
                }
            }
        }
    ]

    # 测试不同的场�?    test_cases = [
        ("简单请�?(�?tools, �?prompt)", {
            "messages": [{"role": "user", "content": "Say 'ok'"}],
            "max_tokens": 16384,
            "include_tools": False
        }),
        ("模拟 Wiki 任务 (�?tools, �?prompt)", {
            "messages": [
                {"role": "system", "content": "你是一位资深的技术文档工程师，擅长为软件项目编写清晰、完整、结构化�?Wiki 文档。你需要：1. 撰写项目概述 2. 编写安装指南 3. 描述系统架构 4. 生成 API 文档 5. 定义开发规�?6. 编写部署指南。所有文档使�?Markdown 格式�?},
                {"role": "user", "content": "Generate project wiki for 'test-project' at /path/to/project. Please analyze the codebase and generate comprehensive documentation including: README.md, docs/getting-started/, docs/development/, docs/deployment/"}
            ],
            "max_tokens": 16384,
            "include_tools": True
        }),
        ("超大 prompt (模拟多轮对话)", {
            "messages": [
                {"role": "system", "content": "你是一位资深的技术文档工程师"},
                {"role": "user", "content": "帮我生成文档"},
                {"role": "assistant", "content": "好的，我会帮你生成文档。请问你希望生成哪些类型的文档？"},
                {"role": "user", "content": "我需要完整的项目文档，包�?README、安装指南、架构文档、API 文档、开发规范和部署指南"},
                {"role": "assistant", "content": "明白。让我先分析项目结构"},
                {"role": "user", "content": "项目路径�?/path/to/project，请开始分�?},
            ],
            "max_tokens": 16384,
            "include_tools": True
        }),
    ]

    results = []

    for desc, test_config in test_cases:
        payload = {
            "model": "gpt-5-mini",
            "messages": test_config["messages"],
            "max_tokens": test_config["max_tokens"],
            "temperature": 0.7,
            "n": 1,
        }
        if test_config["include_tools"]:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        print(f"\n🚀 测试 {desc}...")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    COPILOT_CHAT_URL,
                    headers=headers,
                    json=payload
                )

                status = response.status_code
                results.append((desc, status))

                if status == 200:
                    print(f"   �?成功")
                    # 尝试解析响应，查看实际返回的 tokens
                    try:
                        resp_data = response.json()
                        usage = resp_data.get("usage", {})
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        completion_tokens = usage.get("completion_tokens", 0)
                        total_tokens = usage.get("total_tokens", 0)
                        print(f"   📊 Token 使用: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
                    except:
                        pass
                elif status == 429:
                    print(f"   �?429 Rate Limit")
                    # 打印详细错误信息
                    try:
                        resp_text = response.text
                        print(f"   📄 错误响应: {resp_text[:200]}")
                    except:
                        pass
                elif status == 500:
                    print(f"   �?500 Internal Server Error")
                    try:
                        resp_text = response.text
                        print(f"   📄 错误响应: {resp_text[:200]}")
                    except:
                        pass
                else:
                    print(f"   ⚠️ {status}")

        except Exception as e:
            print(f"   �?错误: {e}")
            results.append((desc, f"Error: {e}"))

    # 打印总结
    print(f"\n{'='*60}")
    print(f"测试结果总结:")
    print(f"{'='*60}")
    for desc, status in results:
        icon = "�? if status == 200 else "�?
        print(f"{icon} {desc}: {status}")
    print(f"{'='*60}")

    # 对最后一个测试用例做详细响应打印（带 tools 的复杂场景）
    last_desc, last_test_config = test_cases[-1]
    last_payload = {
        "model": "gpt-5-mini",
        "messages": last_test_config["messages"],
        "max_tokens": last_test_config["max_tokens"],
        "temperature": 0.7,
        "n": 1,
    }
    if last_test_config["include_tools"]:
        last_payload["tools"] = tools
        last_payload["tool_choice"] = "auto"

    print(f"\n🔍 详细响应分析 (最后一个测试用�?: {last_desc}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                COPILOT_CHAT_URL,
                headers=headers,
                json=last_payload
            )

            print(f"📊 响应状态码: {response.status_code}")
            print(f"📊 响应�?")

            # 打印关键响应�?            for key in ['retry-after', 'x-ratelimit-remaining', 'x-ratelimit-limit', 'x-ratelimit-used', 'x-request-id']:
                value = response.headers.get(key)
                if value:
                    print(f"   - {key}: {value}")

            print(f"\n📊 响应内容:")
            try:
                resp_json = response.json()
                print(f"   {json.dumps(resp_json, indent=2, ensure_ascii=False)[:800]}")
            except:
                print(f"   {response.text[:800]}")

            if response.status_code == 429:
                print(f"\n�?⚠️ 429 Rate Limit 触发!")
            elif response.status_code == 200:
                print(f"\n�?请求成功!")
            else:
                print(f"\n⚠️ 异常状态码: {response.status_code}")

    except httpx.HTTPStatusError as e:
        print(f"\n�?HTTP 错误: {e}")
        print(f"   状态码: {e.response.status_code}")
        print(f"   响应: {e.response.text[:300]}")
    except Exception as e:
        print(f"\n�?请求失败: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主函�?""
    print("GitHub Copilot 429 错误诊断工具")
    print(f"Pool 目录: {POOL_DIR}")

    if not POOL_DIR.exists():
        print(f"�?Pool 目录不存�?)
        return

    # 查找所�?slot
    slot_files = sorted(POOL_DIR.glob("slot_*.json"))
    if not slot_files:
        print(f"�?没有找到任何 slot")
        return

    print(f"📦 找到 {len(slot_files)} �?slot")

    # 测试每个 slot
    tasks = []
    for slot_file in slot_files:
        slot_id = int(slot_file.stem.split('_')[1])
        tasks.append(test_slot(slot_id))

    # 串行测试（避免并发影响）
    for task in tasks:
        await task

    print(f"\n{'='*60}")
    print("�?测试完成")
    print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(main())
