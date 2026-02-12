"""测试 Provider 配置是否正确加载"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from nanobot.config.schema import load_config
from nanobot.providers.factory import create_llm_provider
from nanobot.core.dependencies import get_component_manager

def test_config_loading():
    """测试配置加载"""
    print("=" * 60)
    print("测试 1: 配置加载")
    print("=" * 60)

    config = load_config()

    print("\nProvider 配置:")
    print(f"  vLLM API Base: {config.providers.vllm.api_base}")
    print(f"  vLLM API Key: {config.providers.vllm.api_key[:10] if config.providers.vllm.api_key else 'None'}...")
    print(f"  火山引擎 API Key: {config.providers.zhipu.api_key[:10] if config.providers.zhipu.api_key else 'None'}...")
    print(f"  OpenAI API Key: {config.providers.openai.api_key[:10] if config.providers.openai.api_key else 'None'}...")

    print(f"\n默认模型: {config.agents.defaults.model}")

    return config

def test_factory_creation(config):
    """测试工厂创建 Provider"""
    print("\n" + "=" * 60)
    print("测试 2: Provider 工厂创建")
    print("=" * 60)

    provider = create_llm_provider(config)

    if provider:
        print(f"\n✓ 成功创建 Provider")
        print(f"  类型: {type(provider).__name__}")
        print(f"  默认模型: {provider.get_default_model()}")
    else:
        print(f"\n✗ 没有配置任何 Provider")

    return provider

def test_component_manager():
    """测试组件管理器"""
    print("\n" + "=" * 60)
    print("测试 3: 组件管理器")
    print("=" * 60)

    manager = get_component_manager()

    # 测试获取 Provider
    provider = manager.get_llm_provider()

    if provider:
        print(f"\n✓ 成功获取 Provider")
        print(f"  类型: {type(provider).__name__}")
        print(f"  默认模型: {provider.get_default_model()}")

        # 测试 AgentLoop
        import asyncio
        async def test_agent_loop():
            agent_loop = await manager.get_agent_loop()
            print(f"\n✓ 成功创建 AgentLoop")
            print(f"  模型: {agent_loop.model}")
            print(f"  最大迭代次数: {agent_loop.max_iterations}")

        asyncio.run(test_agent_loop())
    else:
        print(f"\n✗ 没有可用的 Provider")

def main():
    """主测试函数"""
    print("\n🧪 Provider 配置测试\n")

    try:
        config = test_config_loading()
        test_factory_creation(config)
        test_component_manager()

        print("\n" + "=" * 60)
        print("✅ 所有测试通过")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
