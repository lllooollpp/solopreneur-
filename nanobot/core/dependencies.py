"""
依赖注入和全局实例管理
提供单例模式管理核心组件
"""
from typing import Optional
import threading
from pathlib import Path
from loguru import logger


class ComponentManager:
    """
    全局组件管理器（单例模式）
    管理所有核心组件的生命周期
    """

    _instance: Optional['ComponentManager'] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._config: Optional = None
        self._agent_loop: Optional = None
        self._copilot_provider: Optional = None
        self._llm_provider: Optional = None
        self._message_bus: Optional = None
        self._agent_manager: Optional = None

        self._initialized = True
        logger.debug("ComponentManager initialized")

    # ==================== Config ====================

    def get_config(self, force_reload: bool = False):
        """获取配置"""
        from nanobot.config.loader import load_config

        if self._config is None or force_reload:
            self._config = load_config()
        return self._config

    # ==================== Providers ====================

    def get_copilot_provider(self):
        """获取 GitHub Copilot Provider"""
        if self._copilot_provider is None:
            from nanobot.providers.github_copilot import GitHubCopilotProvider
            config = self.get_config()
            self._copilot_provider = GitHubCopilotProvider(config=config)
        return self._copilot_provider

    def get_llm_provider(self, force_copilot: bool = False):
        """
        获取 LLM Provider

        Args:
            force_copilot: 强制使用 Copilot Provider
        """
        # 优先使用已认证的 Copilot
        if force_copilot:
            copilot = self.get_copilot_provider()
            if copilot.session:
                return copilot

        # 否则使用配置的 Provider
        if self._llm_provider is None:
            config = self.get_config()
            from nanobot.providers.litellm_provider import LiteLLMProvider
            api_key = config.get_api_key()
            api_base = config.get_api_base()
            self._llm_provider = LiteLLMProvider(
                api_key=api_key,
                api_base=api_base,
                default_model=config.agents.defaults.model
            )

        return self._llm_provider

    # ==================== Message Bus ====================

    def get_message_bus(self):
        """获取消息总线"""
        if self._message_bus is None:
            from nanobot.bus.queue import MessageBus
            self._message_bus = MessageBus()
        return self._message_bus

    # ==================== Agent Manager ====================

    def get_agent_manager(self):
        """获取 Agent Manager"""
        if self._agent_manager is None:
            from nanobot.agent.definitions.manager import AgentManager
            config = self.get_config()
            self._agent_manager = AgentManager(workspace=config.workspace_path)
        return self._agent_manager

    # ==================== Agent Loop ====================

    async def get_agent_loop(self):
        """获取或创建 AgentLoop（异步）"""
        if self._agent_loop is not None:
            return self._agent_loop

        from nanobot.agent.core.loop import AgentLoop
        from nanobot.agent.core.context import ContextBuilder
        from nanobot.agent.core.compaction import CompactionEngine
        from nanobot.workflow.engine import WorkflowEngine

        config = self.get_config()

        # 选择 Provider
        provider = self.get_llm_provider(force_copilot=True)

        self._agent_loop = AgentLoop(
            bus=self.get_message_bus(),
            provider=provider,
            workspace=config.workspace_path,
            model=config.agents.defaults.model,
            max_iterations=config.agents.defaults.max_tool_iterations,
            brave_api_key=config.tools.web.search.api_key or None,
            exec_config=config.tools.exec,
            max_session_tokens=config.agents.defaults.max_tokens_per_session,
            max_total_time=config.agents.defaults.agent_timeout,
        )

        return self._agent_loop

    # ==================== Lifecycle ====================

    async def shutdown(self):
        """关闭所有组件"""
        logger.info("Shutting down ComponentManager...")

        if self._copilot_provider:
            try:
                await self._copilot_provider.close()
                logger.info("Copilot provider closed")
            except Exception as e:
                logger.error(f"Error closing copilot provider: {e}")

        self._agent_loop = None
        self._llm_provider = None
        self._message_bus = None
        self._agent_manager = None

        logger.info("ComponentManager shutdown complete")

    def reset(self):
        """重置所有组件（用于测试或重新加载）"""
        logger.info("Resetting ComponentManager...")
        self._agent_loop = None
        self._llm_provider = None
        self._message_bus = None
        self._agent_manager = None
        # 不重置 _copilot_provider，保持认证状态
        logger.debug("ComponentManager reset complete")


# 全局实例
_component_manager: Optional[ComponentManager] = None
_manager_lock = threading.Lock()


def get_component_manager() -> ComponentManager:
    """获取全局组件管理器"""
    global _component_manager
    if _component_manager is None:
        with _manager_lock:
            if _component_manager is None:
                _component_manager = ComponentManager()
    return _component_manager


def reset_component_manager():
    """重置组件管理器"""
    global _component_manager
    with _manager_lock:
        _component_manager = None
