"""诊断 Provider 配置问题"""
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))


def print_section(title):
    """打印分隔�?""
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def check_config_file():
    """检查配置文�?""
    print_section("📁 配置文件检�?)

    config_paths = [
        Path.home() / ".solopreneur" / "config.json",
        Path(".solopreneur") / "config.json",
        Path("config.json"),
    ]

    config_path = None
    for path in config_paths:
        if path.exists():
            config_path = path
            print(f"�?找到配置文件: {path}")
            break

    if not config_path:
        print("�?未找到配置文�?)
        print("\n尝试的路�?")
        for path in config_paths:
            print(f"  - {path}")
        return None

    return config_path


def load_and_analyze_config(config_path):
    """加载并分析配�?""
    print_section("📋 配置内容分析")

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        print(f"\n�?配置文件加载成功")
        print(f"文件大小: {config_path.stat().st_size} bytes")

        # 分析 providers 部分
        if 'providers' not in config:
            print("\n�?配置中缺�?'providers' 字段")
            return None

        providers = config['providers']
        print(f"\n📊 Providers 配置:")

        # 检�?copilot_priority
        copilot_priority = providers.get('copilot_priority', False)
        status_icon = "�? if copilot_priority else "�?
        print(f"  {status_icon} Copilot 优先�? {copilot_priority}")

        if copilot_priority:
            print("\n⚠️  警告：Copilot 优先级已启用")
            print("   这将忽略其他 Provider 配置")

        # 检查其�?Provider
        print("\n  其他 Provider 配置:")

        provider_order = ['vllm', 'zhipu', 'openrouter', 'anthropic', 'openai', 'groq', 'gemini']
        provider_names = {
            'vllm': '本地 OpenAI 标准接口',
            'zhipu': '火山引擎 / 智谱 AI',
            'openrouter': 'OpenRouter',
            'anthropic': 'Anthropic Claude',
            'openai': 'OpenAI',
            'groq': 'Groq',
            'gemini': 'Google Gemini',
        }

        configured_providers = []

        for provider_key in provider_order:
            if provider_key not in providers:
                continue

            provider_config = providers[provider_key]
            api_key = provider_config.get('api_key', '')
            api_base = provider_config.get('api_base', '')

            if api_key or api_base:
                configured_providers.append(provider_key)
                print(f"    �?{provider_names[provider_key]} ({provider_key})")

                if api_key:
                    masked_key = api_key[:8] + "..." if len(api_key) > 8 else "***"
                    print(f"       API Key: {masked_key}")
                if api_base:
                    print(f"       API Base: {api_base}")
            else:
                print(f"    �?{provider_names[provider_key]} ({provider_key}) - 未配�?)

        if not configured_providers:
            print("\n�?未配置任�?Provider")
            return None

        # 显示将被使用�?Provider
        print("\n🎯 将被使用�?Provider:")

        if copilot_priority:
            print("  🐙 GitHub Copilot (优先级已启用)")
            print("   注意：需�?Copilot 账号已登�?)
        else:
            # 找到第一个配置的 Provider
            for provider_key in provider_order:
                if provider_key in configured_providers:
                    print(f"  {provider_names[provider_key]} ({provider_key})")
                    print(f"   模型: {config.get('agents', {}).get('defaults', {}).get('model', '未设�?)}")
                    break

        return config

    except json.JSONDecodeError as e:
        print(f"\n�?配置文件 JSON 格式错误:")
        print(f"   {e}")
        return None
    except Exception as e:
        print(f"\n�?读取配置文件失败:")
        print(f"   {e}")
        return None


def analyze_error():
    """分析错误日志中的问题"""
    print_section("🔍 错误日志分析")

    print("\n错误信息:")
    print("  LLMAPIError: API调用失败: litellm.InternalServerError:")
    print("  InternalServerError: Hosted_vllmException")
    print("  - Cannot connect to host 10.104.6.197:38099")
    print("  - ssl:default [Connect call failed ('10.104.6.197', 38099)]")

    print("\n🔬 问题诊断:")

    print("\n1. 连接目标:")
    print("   - 主机: 10.104.6.197")
    print("   - 端口: 38099")
    print("   - 协议: HTTP (�?SSL)")

    print("\n2. 错误类型:")
    print("   - 连接被拒�?(Connect call failed)")

    print("\n3. 可能的原�?")
    print("   a) 服务器未运行")
    print("      - 目标服务�?10.104.6.197:38099 可能没有启动")
    print("      - 请检�?vLLM 服务器是否正在运�?)
    print()
    print("   b) 网络问题")
    print("      - 无法访问 10.104.6.197")
    print("      - 检查网络连接和防火�?)
    print()
    print("   c) 配置错误")
    print("      - API Base 地址可能不正�?)
    print("      - 端口号可能不�?)
    print()
    print("   d) 服务未监�?)
    print("      - vLLM 可能未在 38099 端口启动")
    print("      - 检�?vLLM 启动时的输出")

    print("\n💡 解决方案:")

    print("\n方案 1: 检查服务器状�?)
    print("  在服务器机器上运�?")
    print("    curl http://10.104.6.197:38099/v1/models")
    print("    �?)
    print("    netstat -tuln | grep 38099")

    print("\n方案 2: 修改配置")
    print("  如果地址不正确，请修改配�?")
    print("    ~/.solopreneur/config.json")
    print("  修改 providers.vllm.api_base 为正确的地址")

    print("\n方案 3: 使用本地测试")
    print("  如果你有本地 vLLM:")
    print("    1. 确认本地 vLLM 地址: http://localhost:8000/v1")
    print("    2. 修改配置文件中的 api_base")
    print("    3. 运行测试: python quick_test.py http://localhost:8000/v1 dummy llama-3-8b")


def suggest_test_commands(api_base):
    """建议测试命令"""
    print_section("🧪 建议的测试命�?)

    print(f"\n当前配置�?API Base: {api_base}")

    print("\n1. 使用 curl 测试连接:")
    print(f"   curl {api_base}/models")

    print("\n2. 使用快速测试脚�?")
    print(f"   python quick_test.py {api_base} dummy llama-3-8b")

    print("\n3. 完整 Provider 测试:")
    print("   python test_llm_connection.py")

    print("\n4. 检查配�?")
    print("   python diagnose_provider.py")


def main():
    """主函�?""
    import sys
    import io

    # 设置 UTF-8 编码
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    print("\n[诊断] Provider 配置诊断工具")
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 1. 检查配置文�?    config_path = check_config_file()

    if not config_path:
        print("\n�?无法继续：配置文件不存在")
        return

    # 2. 加载并分析配�?    config = load_and_analyze_config(config_path)

    if not config:
        print("\n�?无法继续：配置文件有问题")
        return

    # 3. 分析错误
    analyze_error()

    # 4. 建议测试命令
    api_base = config.get('providers', {}).get('vllm', {}).get('api_base', '未配�?)
    suggest_test_commands(api_base)

    print_section("�?诊断完成")
    print("\n请根据上面的建议进行排查�?)


if __name__ == "__main__":
    main()
