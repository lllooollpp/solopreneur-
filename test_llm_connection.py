"""测试 LLM Provider 连接和调用"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from nanobot.config.schema import load_config
from nanobot.providers.factory import create_llm_provider
from loguru import logger


async def test_provider():
    """测试 Provider 连接和简单调用"""
    print("\n" + "=" * 70)
    print("🧪 LLM Provider 连接测试")
    print("=" * 70)

    # 1. 加载配置
    print("\n[1/5] 加载配置...")
    config = load_config()

    print("\n📋 当前 Provider 配置:")
    providers_config = config.providers
    print(f"  - Copilot 优先级: {providers_config.copilot_priority}")
    print(f"  - vLLM API Base: {providers_config.vllm.api_base or '未配置'}")
    print(f"  - vLLM API Key: {providers_config.vllm.api_key[:10] + '...' if providers_config.vllm.api_key else '未配置'}")
    print(f"  - 火山引擎 API Key: {providers_config.zhipu.api_key[:10] + '...' if providers_config.zhipu.api_key else '未配置'}")
    print(f"  - OpenAI API Key: {providers_config.openai.api_key[:10] + '...' if providers_config.openai.api_key else '未配置'}")
    print(f"  - Anthropic API Key: {providers_config.anthropic.api_key[:10] + '...' if providers_config.anthropic.api_key else '未配置'}")

    # 2. 检查 Copilot 优先级
    print("\n[2/5] 检查 Provider 优先级...")
    if providers_config.copilot_priority:
        print("  ℹ️  Copilot 优先级已启用")
        print("  ⚠️  注意：Copilot 优先级启用时，将忽略其他 Provider 配置")
    else:
        print("  ℹ️  Copilot 优先级已禁用，将使用配置的其他 Provider")

    # 3. 创建 Provider
    print("\n[3/5] 创建 Provider...")
    provider = create_llm_provider(config)

    if not provider:
        print("  ❌ 未配置任何 LLM Provider")
        print("\n💡 请先配置至少一个 Provider:")
        print("   - 方法 1: 配置管理 → LLM Providers → 选择 Provider → 填写配置")
        print("   - 方法 2: 手动编辑 ~/.nanobot/config.json")
        return False

    print(f"  ✅ 成功创建 Provider: {type(provider).__name__}")

    # 4. 获取默认模型
    print("\n[4/5] 获取默认模型...")
    default_model = provider.get_default_model()
    print(f"  默认模型: {default_model}")

    # 5. 测试简单调用
    print("\n[5/5] 测试模型调用...")
    test_messages = [
        {"role": "user", "content": "你好，请用一句话介绍你自己。"}
    ]

    print(f"  发送消息: {test_messages[0]['content']}")
    print("  等待响应...")

    try:
        result = await provider.chat(
            messages=test_messages,
            model=default_model,
            temperature=0.7,
            max_tokens=100
        )

        # 处理返回结果
        if hasattr(result, 'content'):
            response_text = result.content
        elif isinstance(result, dict):
            choices = result.get("choices", [])
            if choices:
                response_text = choices[0].get("message", {}).get("content", "")
            else:
                response_text = "返回格式异常：没有 choices"
        elif isinstance(result, str):
            response_text = result
        else:
            response_text = f"未知返回类型: {type(result)}"

        print(f"\n  ✅ 调用成功！")
        print(f"\n  📝 模型响应:")
        print(f"  ──────────────────────────────────────────")
        print(f"  {response_text}")
        print(f"  ──────────────────────────────────────────")

        # 显示使用信息
        if hasattr(result, 'usage'):
            print(f"\n  📊 Token 使用:")
            print(f"  {result.usage}")

        return True

    except Exception as e:
        print(f"\n  ❌ 调用失败！")
        print(f"\n  错误类型: {type(e).__name__}")
        print(f"  错误信息: {e}")

        # 针对不同错误给出建议
        error_str = str(e).lower()

        if "cannot connect to host" in error_str or "connection refused" in error_str:
            print("\n💡 连接失败建议:")
            print("  1. 检查 API Base 地址是否正确")
            print("  2. 检查服务器是否正在运行")
            print("  3. 检查网络连接和防火墙设置")
            if "10.104.6.197" in error_str:
                print("  ⚠️  检测到远程服务器地址 10.104.6.197，确认是否正确")

        elif "authentication" in error_str or "api_key" in error_str or "unauthorized" in error_str:
            print("\n💡 认证失败建议:")
            print("  1. 检查 API Key 是否正确")
            print("  2. 确认 API Key 是否有效且未过期")

        elif "model" in error_str or "not found" in error_str:
            print("\n💡 模型错误建议:")
            print("  1. 检查模型名称是否正确")
            print("  2. 确认模型是否在 Provider 中可用")

        elif "rate limit" in error_str or "429" in error_str:
            print("\n💡 速率限制建议:")
            print("  1. 等待一段时间后重试")
            print("  2. 检查 API 使用额度")

        print("\n🔧 当前配置详情:")
        print(f"  - Provider 类型: {type(provider).__name__}")
        print(f"  - API Base: {provider.api_base}")
        print(f"  - API Key: {provider.api_key[:10] + '...' if provider.api_key and len(provider.api_key) > 10 else provider.api_key}")
        print(f"  - 默认模型: {provider.get_default_model()}")

        return False


async def test_specific_provider(provider_type: str, api_key: str, api_base: str, model: str):
    """测试特定 Provider 配置"""
    print("\n" + "=" * 70)
    print(f"🧪 测试特定 Provider: {provider_type}")
    print("=" * 70)

    from nanobot.providers.litellm_provider import LiteLLMProvider

    print(f"\n配置:")
    print(f"  - Provider: {provider_type}")
    print(f"  - API Base: {api_base}")
    print(f"  - API Key: {api_key[:10] + '...' if api_key and len(api_key) > 10 else api_key}")
    print(f"  - 模型: {model}")

    try:
        provider = LiteLLMProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=model
        )

        test_messages = [
            {"role": "user", "content": "Hello! Please say 'Connection successful' in response."}
        ]

        print("\n发送测试消息...")
        result = await provider.chat(
            messages=test_messages,
            model=model,
            temperature=0.5,
            max_tokens=50
        )

        response_text = result.content if hasattr(result, 'content') else str(result)

        print(f"\n✅ 连接成功！")
        print(f"\n模型响应:")
        print(f"  {response_text}")

        return True

    except Exception as e:
        print(f"\n❌ 连接失败！")
        print(f"\n错误: {e}")
        return False


def main():
    """主测试函数"""
    print("\n🚀 LLM Provider 连接测试工具\n")

    # 检查命令行参数
    if len(sys.argv) > 1:
        # 测试特定配置
        if sys.argv[1] == "--custom":
            if len(sys.argv) < 6:
                print("用法: python test_llm_connection.py --custom <provider_type> <api_key> <api_base> <model>")
                print("\n示例:")
                print("  python test_llm_connection.py --custom vllm dummy http://localhost:8000/v1 llama-3-8b")
                return

            provider_type = sys.argv[2]
            api_key = sys.argv[3]
            api_base = sys.argv[4] if sys.argv[4] != "none" else None
            model = sys.argv[5]

            asyncio.run(test_specific_provider(provider_type, api_key, api_base, model))
        else:
            print(f"未知参数: {sys.argv[1]}")
            print("使用方法:")
            print("  python test_llm_connection.py              # 测试配置文件中的 Provider")
            print("  python test_llm_connection.py --custom ...  # 测试自定义配置")
    else:
        # 测试配置文件中的 Provider
        success = asyncio.run(test_provider())

        print("\n" + "=" * 70)
        if success:
            print("✅ 测试完成：Provider 连接正常")
        else:
            print("❌ 测试失败：请检查配置和连接")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
