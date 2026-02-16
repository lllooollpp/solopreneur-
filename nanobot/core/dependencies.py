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
        from nanobot.utils.helpers import get_project_root

        if self._config is None or force_reload:
            self._config = load_config()

            # 统一工作区到当前项目根目录（避免使用 ~ / Home 路径）
            project_root = get_project_root()
            self._config.agents.defaults.workspace = str(project_root)
        return self._config

    # ==================== Providers ====================

    def get_copilot_provider(self):
        """获取 GitHub Copilot Provider"""
        if self._copilot_provider is None:
            from nanobot.providers.github_copilot import GitHubCopilotProvider
            config = self.get_config()
            self._copilot_provider = GitHubCopilotProvider(
                config=config,
                default_model=config.agents.defaults.model
            )
        return self._copilot_provider

    def get_llm_provider(self, force_copilot: bool = False):
        """
        获取 LLM Provider

        Args:
            force_copilot: 强制使用 Copilot Provider（忽略其他 Provider 配置）

        Returns:
            LLM Provider 实例
        """
        # 如果强制使用 Copilot，检查 Copilot 是否已认证
        if force_copilot:
            copilot = self.get_copilot_provider()
            if copilot.session:
                logger.info("使用 GitHub Copilot Provider (强制)")
                return copilot

        # 检查配置中的 copilot_priority
        config = self.get_config()
        copilot_priority = getattr(config.providers, 'copilot_priority', False)

        # 如果配置了 copilot_priority，优先使用 Copilot
        if copilot_priority:
            copilot = self.get_copilot_provider()
            if copilot.session:
                logger.info("使用 GitHub Copilot Provider (配置优先)")
                return copilot

        # 默认情况下：优先使用配置的 Provider（本地/火山引擎等）
        if self._llm_provider is None:
            from nanobot.providers.factory import create_llm_provider
            self._llm_provider = create_llm_provider(
                config,
                default_model=config.agents.defaults.model
            )

            # 如果创建了 LiteLLM Provider，记录日志
            if self._llm_provider:
                logger.info("使用配置的 LLM Provider")
            else:
                # 如果没有配置任何 Provider，回退到 Copilot
                copilot = self.get_copilot_provider()
                if copilot.session:
                    logger.info("未配置其他 Provider，回退到 GitHub Copilot")
                    self._llm_provider = copilot

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
            workspace = config.workspace_path
            workspace.mkdir(parents=True, exist_ok=True)
            (workspace / "agents").mkdir(parents=True, exist_ok=True)
            (workspace / "skills").mkdir(parents=True, exist_ok=True)
            logger.info(f"统一工作区路径: {workspace}")
            self._agent_manager = AgentManager(workspace=workspace)
        return self._agent_manager

    # ==================== Agent Loop ====================

    async def get_agent_loop(self):
        """获取或创建 AgentLoop（异步）"""
        if self._agent_loop is not None:
            return self._agent_loop

        from nanobot.agent.core.loop import AgentLoop
        from nanobot.agent.core.context import ContextBuilder
        from nanobot.agent.core.compaction import CompactionEngine
        from nanobot.agent.core.validator import ValidatorConfig
        from nanobot.workflow.engine import WorkflowEngine

        config = self.get_config()

        # 选择 Provider（不再强制使用 Copilot，使用配置的 Provider）
        provider = self.get_llm_provider()

        # 构建验证器配置
        validator_cfg = config.agents.defaults.task_validator
        validator_config = ValidatorConfig(
            enabled=validator_cfg.enabled,
            min_iterations=validator_cfg.min_iterations,
            check_feature_status=validator_cfg.check_feature_status,
            check_git_clean=validator_cfg.check_git_clean,
            check_tests_passed=validator_cfg.check_tests_passed,
            max_continuation_prompts=validator_cfg.max_continuation_prompts,
            use_ai_validation=validator_cfg.use_ai_validation,
            ai_validation_threshold=validator_cfg.ai_validation_threshold,
        )

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
            validator_config=validator_config,
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
