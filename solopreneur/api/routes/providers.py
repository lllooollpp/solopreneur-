"""
Providers API 路由
提供 LLM Provider 配置管理
"""
from typing import Literal

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

from solopreneur.core.dependencies import get_component_manager
from solopreneur.config.loader import save_config

router = APIRouter(prefix="/config", tags=["providers"])


class ProviderConfig(BaseModel):
    """单个 Provider 配置"""
    api_key: str = ""
    api_base: str | None = None


class ProvidersConfig(BaseModel):
    """所有 Providers 配置"""
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    copilot_priority: bool = False


class AgentDefaults(BaseModel):
    """Agent 默认配置"""
    model: str = "gpt-5-mini"
    max_tokens: int = 8192
    temperature: float = 0.7
    review_mode: Literal["auto", "manual"] = "auto"


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    provider: str
    config: ProviderConfig


class TestConnectionResponse(BaseModel):
    """测试连接响应"""
    success: bool
    error: str | None = None


@router.get("/providers")
async def get_providers_config() -> ProvidersConfig:
    """获取所有 Providers 配置"""
    manager = get_component_manager()
    config = manager.get_config()

    return ProvidersConfig(
        anthropic=ProviderConfig(
            api_key=config.providers.anthropic.api_key,
            api_base=config.providers.anthropic.api_base
        ),
        openai=ProviderConfig(
            api_key=config.providers.openai.api_key,
            api_base=config.providers.openai.api_base
        ),
        openrouter=ProviderConfig(
            api_key=config.providers.openrouter.api_key,
            api_base=config.providers.openrouter.api_base
        ),
        groq=ProviderConfig(
            api_key=config.providers.groq.api_key,
            api_base=config.providers.groq.api_base
        ),
        zhipu=ProviderConfig(
            api_key=config.providers.zhipu.api_key,
            api_base=config.providers.zhipu.api_base
        ),
        vllm=ProviderConfig(
            api_key=config.providers.vllm.api_key,
            api_base=config.providers.vllm.api_base
        ),
        gemini=ProviderConfig(
            api_key=config.providers.gemini.api_key,
            api_base=config.providers.gemini.api_base
        ),
        copilot_priority=config.providers.copilot_priority,
    )


@router.post("/providers")
async def update_providers_config(config: ProvidersConfig):
    """更新 Providers 配置"""
    manager = get_component_manager()
    current_config = manager.get_config()

    # 更新配置
    current_config.providers.anthropic.api_key = config.anthropic.api_key
    current_config.providers.anthropic.api_base = config.anthropic.api_base

    current_config.providers.openai.api_key = config.openai.api_key
    current_config.providers.openai.api_base = config.openai.api_base

    current_config.providers.openrouter.api_key = config.openrouter.api_key
    current_config.providers.openrouter.api_base = config.openrouter.api_base

    current_config.providers.groq.api_key = config.groq.api_key
    current_config.providers.groq.api_base = config.groq.api_base

    current_config.providers.zhipu.api_key = config.zhipu.api_key
    current_config.providers.zhipu.api_base = config.zhipu.api_base

    current_config.providers.vllm.api_key = config.vllm.api_key
    current_config.providers.vllm.api_base = config.vllm.api_base

    current_config.providers.gemini.api_key = config.gemini.api_key
    current_config.providers.gemini.api_base = config.gemini.api_base

    current_config.providers.copilot_priority = config.copilot_priority

    # 保存到文件
    save_config(current_config)

    # 重置组件管理器以应用新配置
    manager.reset()
    logger.info("Providers 配置已更新")


@router.get("/agent-defaults")
async def get_agent_defaults() -> AgentDefaults:
    """获取 Agent 默认配置"""
    manager = get_component_manager()
    config = manager.get_config()

    return AgentDefaults(
        model=config.agents.defaults.model,
        max_tokens=config.agents.defaults.max_tokens,
        temperature=config.agents.defaults.temperature,
        review_mode=config.agents.defaults.review_mode,
    )


@router.post("/agent-defaults")
async def update_agent_defaults(config: AgentDefaults):
    """更新 Agent 默认配置"""
    manager = get_component_manager()
    current_config = manager.get_config()

    current_config.agents.defaults.model = config.model
    current_config.agents.defaults.max_tokens = config.max_tokens
    current_config.agents.defaults.temperature = config.temperature
    current_config.agents.defaults.review_mode = config.review_mode

    # 保存到文件
    save_config(current_config)

    # 重置组件管理器以应用新配置
    manager.reset()
    logger.info(
        f"Agent 默认配置已更新: model={config.model}, max_tokens={config.max_tokens}, review_mode={config.review_mode}"
    )


class MemorySearchConfigPayload(BaseModel):
    """Memory Search 配置"""
    enabled: bool = True
    embedding_provider: str = "local"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: str = "auto"
    embedding_api_key: str = ""
    embedding_api_base: str = ""
    embedding_dimension: int = 384
    embedding_batch_size: int = 64
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    max_chunk_size: int = 1200
    min_chunk_size: int = 100
    top_k: int = 5
    min_score: float = 0.1
    auto_index_on_start: bool = True


@router.get("/memory-search")
async def get_memory_search_config() -> MemorySearchConfigPayload:
    """获取 Memory Search 配置"""
    manager = get_component_manager()
    config = manager.get_config()
    ms = config.memory_search

    return MemorySearchConfigPayload(
        enabled=ms.enabled,
        embedding_provider=ms.embedding_provider,
        embedding_model=ms.embedding_model,
        embedding_device=ms.embedding_device,
        embedding_api_key=ms.embedding_api_key,
        embedding_api_base=ms.embedding_api_base,
        embedding_dimension=ms.embedding_dimension,
        embedding_batch_size=ms.embedding_batch_size,
        vector_weight=ms.vector_weight,
        keyword_weight=ms.keyword_weight,
        max_chunk_size=ms.max_chunk_size,
        min_chunk_size=ms.min_chunk_size,
        top_k=ms.top_k,
        min_score=ms.min_score,
        auto_index_on_start=ms.auto_index_on_start,
    )


@router.post("/memory-search")
async def update_memory_search_config(payload: MemorySearchConfigPayload):
    """更新 Memory Search 配置"""
    manager = get_component_manager()
    current_config = manager.get_config()
    ms = current_config.memory_search

    ms.enabled = payload.enabled
    ms.embedding_provider = payload.embedding_provider
    ms.embedding_model = payload.embedding_model
    ms.embedding_device = payload.embedding_device
    ms.embedding_api_key = payload.embedding_api_key
    ms.embedding_api_base = payload.embedding_api_base
    ms.embedding_dimension = payload.embedding_dimension
    ms.embedding_batch_size = payload.embedding_batch_size
    ms.vector_weight = payload.vector_weight
    ms.keyword_weight = payload.keyword_weight
    ms.max_chunk_size = payload.max_chunk_size
    ms.min_chunk_size = payload.min_chunk_size
    ms.top_k = payload.top_k
    ms.min_score = payload.min_score
    ms.auto_index_on_start = payload.auto_index_on_start

    save_config(current_config)
    manager.reset()
    logger.info("Memory Search 配置已更新")

    return {"status": "ok", "message": "Memory Search 配置已保存"}


@router.post("/providers/test", response_model=TestConnectionResponse)
async def test_provider_connection(request: TestConnectionRequest) -> TestConnectionResponse:
    """
    测试 Provider 连接

    发送一个简单的测试请求验证配置是否有效
    """
    try:
        from solopreneur.providers.litellm_provider import LiteLLMProvider

        # 选择测试用的模型
        test_models = {
            "openai": "gpt-4o-mini",
            "vllm": "dummy",  # vLLM 需要用户自己配置模型
            "zhipu": "glm-4",
            "openrouter": "anthropic/claude-3.5-sonnet",
            "groq": "llama-3.1-8b-instant",
            "gemini": "gemini-1.5-flash",
            "anthropic": "claude-3-haiku-20240307"
        }

        test_model = test_models.get(request.provider, "gpt-4o-mini")

        # 创建 Provider
        provider = LiteLLMProvider(
            api_key=request.config.api_key,
            api_base=request.config.api_base,
            default_model=test_model
        )

        # 发送测试请求（简单问候）
        test_message = [{"role": "user", "content": "Hi"}]

        # 对于 vLLM，使用用户可能配置的模型
        if request.provider == "vllm" and request.config.api_base:
            # vLLM 通常不需要真实的 api_key，但我们需要一个虚拟值
            # 不发送真实请求，只验证 API base 是否可达
            import httpx
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    # 尝试获取模型列表（OpenAI 兼容接口）
                    models_url = f"{request.config.api_base.rstrip('/')}/models"
                    response = await client.get(models_url)
                    if response.status_code < 500:
                        return TestConnectionResponse(success=True)
                    return TestConnectionResponse(success=False, error=f"API 返回状态码: {response.status_code}")
            except Exception as e:
                return TestConnectionResponse(success=False, error=f"连接失败: {str(e)}")

        # 其他 Provider 发送真实测试请求
        try:
            await provider.chat(
                messages=test_message,
                max_tokens=10,
            )
            return TestConnectionResponse(success=True)
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "unauthorized" in error_msg.lower():
                error_msg = "API Key 认证失败"
            elif "rate limit" in error_msg.lower():
                error_msg = "速率限制或配额不足"
            elif "timeout" in error_msg.lower():
                error_msg = "请求超时"
            return TestConnectionResponse(success=False, error=error_msg)

    except Exception as e:
        logger.error(f"测试 Provider 连接失败: {e}")
        return TestConnectionResponse(success=False, error=f"测试失败: {str(e)}")
