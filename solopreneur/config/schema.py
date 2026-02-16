"""Configuration schema using Pydantic."""

from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class WhatsAppConfig(BaseModel):
    """WhatsApp channel configuration."""
    enabled: bool = False
    bridge_url: str = "ws://localhost:3001"
    allow_from: list[str] = Field(default_factory=list)  # Allowed phone numbers


class TelegramConfig(BaseModel):
    """Telegram channel configuration."""
    enabled: bool = False
    token: str = ""  # Bot token from @BotFather
    allow_from: list[str] = Field(default_factory=list)  # Allowed user IDs or usernames

class WeComConfig(BaseModel):
    """企业微信通道配置"""
    enabled: bool = False
    corp_id: str = ""  # 企业 ID
    agent_id: str = ""  # 应用 ID
    secret: str = ""  # 应用密钥（用于发送消息）
    token: str = ""  # 接口验证 Token（用于接收消息）
    aes_key: str = ""  # 消息加密密钥（Base64 编码�?3位）


class ChannelsConfig(BaseModel):
    """Configuration for chat channels."""
    whatsapp: WhatsAppConfig = Field(default_factory=WhatsAppConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    wecom: WeComConfig = Field(default_factory=WeComConfig)


class TaskValidatorConfig(BaseModel):
    """任务完成验证器配�?""
    enabled: bool = True  # 是否启用验证�?
    min_iterations: int = 2  # 最小迭代次数（防止过早退出）
    check_feature_status: bool = True  # 检�?feature_list 状�?
    check_git_clean: bool = True  # 检�?working tree
    check_tests_passed: bool = False  # 检查测试通过（可选，较耗时�?
    max_continuation_prompts: int = 3  # 最大继续提示次�?
    # AI 驱动验证配置
    use_ai_validation: bool = True  # 是否使用 AI 验证（推荐）
    ai_validation_threshold: int = 80  # AI 认为完成的阈值分数（0-100�?


class AgentDefaults(BaseModel):
    """Default agent configuration."""
    workspace: str = "~/.nanobot/workspace"
    model: str = "claude-sonnet-4"
    max_tokens: int = 8192
    temperature: float = 0.7
    max_tool_iterations: int = 20
    max_subagents: int = 5  # 最大并发子Agent�?
    review_mode: Literal["auto", "manual"] = "auto"  # 审批模式：自�?人工
    session_cache_size: int = 100  # Session LRU缓存大小
    agent_timeout: int = 1800  # Agent执行总超时（秒）�?0分钟
    max_tokens_per_session: int = 500000  # 每个会话最大Token消耗（超限后自动压缩上下文继续执行�?
    task_validator: TaskValidatorConfig = Field(default_factory=TaskValidatorConfig)  # 任务完成验证�?


class AgentsConfig(BaseModel):
    """Agent configuration."""
    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(BaseModel):
    """LLM provider configuration."""
    api_key: str = ""
    api_base: str | None = None


class ProvidersConfig(BaseModel):
    """Configuration for LLM providers."""
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    copilot_priority: bool = False  # 是否优先使用 Copilot


class GatewayConfig(BaseModel):
    """Gateway/server configuration."""
    host: str = "0.0.0.0"
    port: int = 18790


class WebSearchConfig(BaseModel):
    """Web search tool configuration."""
    api_key: str = ""  # Brave Search API key
    max_results: int = 5
    timeout: int = 10  # HTTP请求超时（秒�?
    max_query_length: int = 500  # 最大查询长�?


class WebToolsConfig(BaseModel):
    """Web tools configuration."""
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(BaseModel):
    """Shell exec tool configuration."""
    timeout: int = 60
    restrict_to_workspace: bool = False  # If true, block commands accessing paths outside workspace
    whitelist_mode: bool = False  # 如果为True，只允许白名单中的命�?
    max_output_size: int = 10000  # 最大输出大小（字符�?


class ToolsConfig(BaseModel):
    """Tools configuration."""
    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)


class TokenPoolConfig(BaseModel):
    """Token pool configuration for multi-account management."""
    max_tokens_per_day: int = 0  # 每个账号每日最大Token限制�?=无限制）
    max_requests_per_day: int = 0  # 每个账号每日最大请求次数限制（0=无限制）
    max_requests_per_hour: int = 0  # 每个账号每小时最大请求次数限制（0=无限制）
    base_cooldown_seconds: int = 30  # 429错误后基础冷却时间（秒�?
    max_cooldown_seconds: int = 300  # 最大冷却时间（秒）
    dead_threshold: int = 10  # 连续错误多少次标记为DEAD


class Config(BaseSettings):
    """Root configuration for nanobot."""
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    token_pool: TokenPoolConfig = Field(default_factory=TokenPoolConfig)
    
    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()
    
    def get_api_key(self) -> str | None:
        """Get API key in priority order: OpenRouter > Anthropic > OpenAI > Gemini > Zhipu > Groq > vLLM."""
        return (
            self.providers.openrouter.api_key or
            self.providers.anthropic.api_key or
            self.providers.openai.api_key or
            self.providers.gemini.api_key or
            self.providers.zhipu.api_key or
            self.providers.groq.api_key or
            self.providers.vllm.api_key or
            None
        )
    
    def get_api_base(self) -> str | None:
        """Get API base URL if using OpenRouter, Zhipu or vLLM."""
        if self.providers.openrouter.api_key:
            return self.providers.openrouter.api_base or "https://openrouter.ai/api/v1"
        if self.providers.zhipu.api_key:
            return self.providers.zhipu.api_base
        if self.providers.vllm.api_base:
            return self.providers.vllm.api_base
        return None
    
    class Config:
        env_prefix = "NANOBOT_"
        env_nested_delimiter = "__"
