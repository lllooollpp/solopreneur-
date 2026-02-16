"""快速测�?LLM 连接"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from solopreneur.providers.litellm_provider import LiteLLMProvider


async def test_connection(api_base: str, api_key: str, model: str):
    """测试连接"""
    print(f"\n🧪 测试连接...")
    print(f"API Base: {api_base}")
    print(f"API Key: {api_key[:10]}...")
    print(f"Model: {model}")
    print()

    try:
        provider = LiteLLMProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=model
        )

        response = await provider.chat(
            messages=[{"role": "user", "content": "Hello, say 'OK'"}],
            model=model,
            max_tokens=10
        )

        print("�?连接成功�?)
        print(f"响应: {response.content[:100]}...")
        return True

    except Exception as e:
        print(f"�?连接失败: {e}")
        return False


if __name__ == "__main__":
    # 使用命令行参数或默认�?    if len(sys.argv) >= 4:
        api_base = sys.argv[1]
        api_key = sys.argv[2]
        model = sys.argv[3]
    else:
        # 从错误信息中提取的配�?        api_base = "http://10.104.6.197:38099/v1"
        api_key = "dummy"
        model = "llama-3-8b"
        print("使用默认配置（从错误日志推断�?")
        print("  API Base: http://10.104.6.197:38099/v1")
        print("  API Key: dummy")
        print("  Model: llama-3-8b")
        print("\n如需测试其他配置:")
        print("  python quick_test.py <api_base> <api_key> <model>")
        print()

    asyncio.run(test_connection(api_base, api_key, model))
