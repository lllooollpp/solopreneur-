"""
Provider Factory
根据配置创建合适的 LLM Provider
"""
from loguru import logger
from typing import Optional


def create_llm_provider(config, default_model: Optional[str] = None):
    """
    根据配置创建 LLM Provider

    Args:
        config: Config 实例
        default_model: 默认模型名称

    Returns:
        LLM Provider 实例
    """
    from solopreneur.providers.litellm_provider import LiteLLMProvider

    # 优先级顺�?
    # 1. vllm (本地部署)
    # 2. zhipu (火山引擎)
    # 3. openrouter
    # 4. anthropic
    # 5. openai
    # 6. groq
    # 7. gemini

    providers_config = config.providers

    # vLLM (本地 OpenAI 标准接口)
    if providers_config.vllm.api_base:
        logger.info("使用 vLLM Provider (本地 OpenAI 标准接口)")
        return LiteLLMProvider(
            api_key=providers_config.vllm.api_key or "dummy",
            api_base=providers_config.vllm.api_base,
            default_model=default_model or config.agents.defaults.model
        )

    # 火山引擎
    if providers_config.zhipu.api_key:
        logger.info("使用火山引擎 / 智谱 AI Provider")
        return LiteLLMProvider(
            api_key=providers_config.zhipu.api_key,
            api_base=providers_config.zhipu.api_base,
            default_model=default_model or config.agents.defaults.model
        )

    # OpenRouter
    if providers_config.openrouter.api_key:
        logger.info("使用 OpenRouter Provider")
        return LiteLLMProvider(
            api_key=providers_config.openrouter.api_key,
            api_base=providers_config.openrouter.api_base,
            default_model=default_model or config.agents.defaults.model
        )

    # Anthropic Claude
    if providers_config.anthropic.api_key:
        logger.info("使用 Anthropic Claude Provider")
        return LiteLLMProvider(
            api_key=providers_config.anthropic.api_key,
            api_base=providers_config.anthropic.api_base,
            default_model=default_model or config.agents.defaults.model
        )

    # OpenAI
    if providers_config.openai.api_key:
        logger.info("使用 OpenAI Provider")
        return LiteLLMProvider(
            api_key=providers_config.openai.api_key,
            api_base=providers_config.openai.api_base,
            default_model=default_model or config.agents.defaults.model
        )

    # Groq
    if providers_config.groq.api_key:
        logger.info("使用 Groq Provider")
        return LiteLLMProvider(
            api_key=providers_config.groq.api_key,
            api_base=providers_config.groq.api_base,
            default_model=default_model or config.agents.defaults.model
        )

    # Gemini
    if providers_config.gemini.api_key:
        logger.info("使用 Google Gemini Provider")
        return LiteLLMProvider(
            api_key=providers_config.gemini.api_key,
            api_base=providers_config.gemini.api_base,
            default_model=default_model or config.agents.defaults.model
        )

    # 没有配置任何 Provider
    logger.warning("未配置任�?LLM Provider")
    return None
