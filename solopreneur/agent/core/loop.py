"""Agent 循环：核心处理引擎。"""

import asyncio
import json
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from solopreneur.bus.events import InboundMessage, OutboundMessage
from solopreneur.bus.queue import MessageBus
from solopreneur.providers.base import LLMProvider
from solopreneur.agent.core.context import ContextBuilder
from solopreneur.agent.core.compaction import CompactionEngine
from solopreneur.agent.core.tools.registry import ToolRegistry
from solopreneur.agent.core.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from solopreneur.agent.core.tools.db import DBInspectTool
from solopreneur.agent.core.tools.metrics import MetricsInspectTool
from solopreneur.agent.core.tools.repo import GitInspectTool, SearchCodeTool, GitCommandTool
from solopreneur.agent.core.tools.shell import ExecTool
from solopreneur.agent.core.tools.web import WebSearchTool, WebFetchTool
from solopreneur.agent.core.tools.message import MessageTool
from solopreneur.agent.core.tools.spawn import SpawnTool
from solopreneur.agent.core.tools.harness import HarnessTool
from solopreneur.agent.core.tools.project_env import GetProjectEnvTool, SetProjectEnvTool
from solopreneur.agent.core.subagent import SubagentManager
from solopreneur.agent.core.validator import TaskCompletionValidator, ValidatorConfig
from solopreneur.storage import UsagePersistence
from solopreneur.session.manager import SessionManager

if TYPE_CHECKING:
    from solopreneur.agent.core.harness import LongRunningHarness
    from solopreneur.config.schema import ExecToolConfig

# 安全限制常量（默认值，可通过 config 覆盖）
DEFAULT_MAX_TOTAL_TIME = 1800  # 30分钟总时间限制
DEFAULT_MAX_TOKENS_PER_SESSION = 500000  # 每次会话最大Token数
# 自动压缩最大次数
MAX_COMPACTION_ROUNDS = 10
# LLM 调用重试配置
LLM_MAX_RETRIES = 3  # 最大重试次数
LLM_RETRY_BASE_DELAY = 2.0  # 基础重试延迟（秒）
LLM_RETRY_MAX_DELAY = 30.0  # 最大重试延迟（秒）


class AgentLoop:
    """
    Agent 循环是核心处理引擎。
    
    它负责：
    1. 从总线接收消息
    2. 使用历史记录、记忆和技能构建上下文
    3. 调用 LLM
    4. 执行工具调用
    5. 发回响应
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 50,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        max_session_tokens: int = 0,
        max_total_time: int = 0,
        validator_config: "ValidatorConfig | None" = None,
        memory_search_config: dict | None = None,
        history_window: int = 50,
    ):
        from solopreneur.config.schema import ExecToolConfig
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.max_session_tokens = max_session_tokens or DEFAULT_MAX_TOKENS_PER_SESSION
        self.max_total_time = max_total_time or DEFAULT_MAX_TOTAL_TIME
        self.history_window = history_window
        
        self.context = ContextBuilder(workspace, memory_search_config=memory_search_config)
        self.usage_store = UsagePersistence()
        self.sessions = SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
        )
        
        # 任务完成验证器
        self.validator_config = validator_config or ValidatorConfig()
        self.validator = TaskCompletionValidator(
            workspace=workspace,
            harness=None,  # 稍后通过 set_harness 设置
            config=self.validator_config,
            provider=provider,  # 传递 provider 用于 AI 验证
            model=self.model,
        )

        # 三层压缩引擎
        self.compaction = CompactionEngine(
            provider=provider,
            workspace=workspace,
            model=self.model,
        )

        # 延迟导入以避免循环依赖
        from solopreneur.agent.definitions.manager import AgentManager
        from solopreneur.workflow.engine import WorkflowEngine

        # 直接创建 AgentManager（独立实例，不使用组件管理器）
        # 这允许每个 AgentLoop 有自己的 AgentManager
        self.agent_manager = AgentManager(
            workspace=workspace,
            skills_loader=self.context.skills,
        )
        self.workflow_engine = WorkflowEngine(
            subagent_manager=self.subagents,
            agent_manager=self.agent_manager,
            workspace=workspace,
        )
        
        self._running = False
        self._register_default_tools()

    def set_harness(self, harness: "LongRunningHarness | None") -> None:
        """
        设置 LongRunningHarness 实例
        
        用于任务完成验证器检查 feature_list 状态
        同时传递给 WorkflowEngine 以启用 effc.md 增量模式
        """
        self.validator.harness = harness
        self.workflow_engine.set_harness(harness)
        logger.debug(f"Validator & WorkflowEngine harness set: {harness is not None}")

    def _record_usage(
        self,
        session_key: str,
        model: str,
        usage: dict[str, int] | None,
        duration_ms: int,
        is_stream: bool,
    ) -> None:
        """记录一次 LLM 调用 usage（失败不影响主流程）。"""
        usage = usage or {}
        try:
            self.usage_store.record(
                session_key=session_key,
                model=model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                duration_ms=duration_ms,
                is_stream=is_stream,
            )
        except Exception as e:
            logger.warning(f"记录 LLM usage 失败: {e}")
    
    async def _call_llm_with_retry(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        on_chunk: Any = None,
        use_stream: bool = True,
    ) -> tuple[Any, bool]:
        """
        带重试机制的 LLM 调用。

        Args:
            messages: 消息列表
            tools: 工具定义列表
            on_chunk: 流式回调
            use_stream: 是否使用流式调用

        Returns:
            (response, success) - 响应对象和是否成功

        Raises:
            最后一次重试失败后抛出异常
        """
        import random
        from httpx import ReadTimeout, ConnectTimeout, ReadError, ConnectError

        last_error = None

        for attempt in range(LLM_MAX_RETRIES):
            try:
                if use_stream and hasattr(self.provider, "chat_stream") and on_chunk:
                    response = await self.provider.chat_stream(
                        messages=messages,
                        tools=tools,
                        model=self.model,
                        on_chunk=on_chunk,
                    )
                else:
                    response = await self.provider.chat(
                        messages=messages,
                        tools=tools,
                        model=self.model,
                    )
                return response, True

            except (ReadTimeout, ConnectTimeout, ReadError, ConnectError, asyncio.TimeoutError) as e:
                last_error = e
                if attempt < LLM_MAX_RETRIES - 1:
                    # 指数退避 + 随机抖动
                    delay = min(
                        LLM_RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1),
                        LLM_RETRY_MAX_DELAY
                    )
                    logger.warning(
                        f"LLM 调用失败 (尝试 {attempt + 1}/{LLM_MAX_RETRIES}): {type(e).__name__}: {e}。"
                        f"将在 {delay:.1f} 秒后重试..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"LLM 调用失败，已达到最大重试次数 ({LLM_MAX_RETRIES})")
                    raise

            except Exception as e:
                # 其他异常直接抛出，不重试
                logger.error(f"LLM 调用遇到非网络错误: {type(e).__name__}: {e}")
                raise

        # 理论上不会到达这里，但为了类型安全
        if last_error:
            raise last_error
        raise RuntimeError("LLM 调用失败，未知错误")

    def _register_default_tools(self) -> None:
        """注册默认工具集。"""
        # 文件工具（带工作空间限制）
        self.tools.register(ReadFileTool(workspace=self.workspace))
        self.tools.register(WriteFileTool(workspace=self.workspace))
        self.tools.register(EditFileTool(workspace=self.workspace))
        self.tools.register(ListDirTool(workspace=self.workspace))
        self.tools.register(DBInspectTool())
        self.tools.register(MetricsInspectTool())
        self.tools.register(SearchCodeTool(workspace=self.workspace))
        self.tools.register(GitInspectTool(workspace=self.workspace))
        self.tools.register(GitCommandTool(workspace=self.workspace))

        # Harness 工具（长期任务管理）
        self.tools.register(HarnessTool(workspace=self.workspace))
        self.tools.register(GetProjectEnvTool(workspace=self.workspace))
        self.tools.register(SetProjectEnvTool(workspace=self.workspace))

        # Shell 工具
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.exec_config.restrict_to_workspace,
            whitelist_mode=self.exec_config.whitelist_mode,
            console_stream=self.exec_config.console_stream,
        ))
        
        # Web 工具
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())
        
        # 消息工具
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # 衍生辅助工具 (Spawn tool，用于子 agent)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)
        
        # 角色委派工具 (delegate，用于将任务委派给软件工程角色)
        from solopreneur.agent.core.tools.delegate import DelegateTool
        from solopreneur.agent.core.tools.delegate_auto import DelegateAutoTool
        from solopreneur.agent.core.tools.delegate_parallel import DelegateParallelTool
        delegate_tool = DelegateTool(
            manager=self.subagents,
            agent_manager=self.agent_manager,
        )
        self.tools.register(delegate_tool)

        delegate_parallel_tool = DelegateParallelTool(
            manager=self.subagents,
            agent_manager=self.agent_manager,
        )
        self.tools.register(delegate_parallel_tool)

        delegate_auto_tool = DelegateAutoTool(
            manager=self.subagents,
            agent_manager=self.agent_manager,
        )
        self.tools.register(delegate_auto_tool)
        
        # 工作流工具 (run_workflow，用于执行预定义的开发流水线)
        from solopreneur.workflow.engine import RunWorkflowTool, WorkflowControlTool
        workflow_tool = RunWorkflowTool(engine=self.workflow_engine)
        self.tools.register(workflow_tool)
        
        control_tool = WorkflowControlTool(engine=self.workflow_engine)
        self.tools.register(control_tool)

    def _resolve_request_workspace(self, project_info: dict | None) -> Path:
        """根据项目上下文解析本次请求应使用的工作目录。"""
        if project_info and project_info.get("path"):
            try:
                p = Path(str(project_info.get("path"))).expanduser().resolve()
                if p.exists() and p.is_dir():
                    return p
                logger.warning(f"项目路径不存在或不是目录，回退到默认工作区: {p}")
            except Exception as e:
                logger.warning(f"解析项目路径失败，回退到默认工作区: {e}")
        return self.workspace

    def _build_request_tools(self, request_workspace: Path) -> ToolRegistry:
        """为单次请求构建工具注册表，确保文件/命令作用域正确。"""
        tools = ToolRegistry()

        # 路径敏感工具：绑定到当前请求工作目录
        tools.register(ReadFileTool(workspace=request_workspace))
        tools.register(WriteFileTool(workspace=request_workspace))
        tools.register(EditFileTool(workspace=request_workspace))
        tools.register(ListDirTool(workspace=request_workspace))
        tools.register(SearchCodeTool(workspace=request_workspace))
        tools.register(GitInspectTool(workspace=request_workspace))
        tools.register(GitCommandTool(workspace=request_workspace))
        tools.register(HarnessTool(workspace=request_workspace))
        tools.register(GetProjectEnvTool(workspace=request_workspace))
        tools.register(SetProjectEnvTool(workspace=request_workspace))
        tools.register(ExecTool(
            working_dir=str(request_workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.exec_config.restrict_to_workspace,
            whitelist_mode=self.exec_config.whitelist_mode,
            console_stream=self.exec_config.console_stream,
        ))

        # 非路径敏感/状态工具：沿用已注册实例
        for name in [
            "db_inspect", "metrics_inspect", "web_search", "web_fetch",
            "message", "spawn", "delegate", "delegate_parallel", "delegate_auto",
            "run_workflow", "workflow_control",
        ]:
            t = self.tools.get(name)
            if t is not None:
                tools.register(t)

        return tools

    # ── 上下文压缩（委托给 CompactionEngine）─────────────────────────

    async def _compact_context(self, messages: list[dict]) -> list[dict]:
        """
        使用三层压缩引擎压缩上下文。

        1. 先执行微压缩（大型工具输出落盘）
        2. 再执行 LLM 驱动的自动压缩（结构化摘要）

        Returns:
            压缩后的消息列表
        """
        # 层1: 微压缩
        messages = self.compaction.microcompact(messages)

        # 层2: LLM 摘要压缩
        messages = await self.compaction.auto_compact(messages)

        return messages

    async def run(self) -> None:
        """运行 agent 循环，处理总线传来的消息。"""
        self._running = True
        logger.info("Agent 循环已启动")
        
        while self._running:
            try:
                # 等待下一条消息
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                
                # 处理消息
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"处理消息时出错: {e}")
                    # 发送错误响应
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"抱歉，我遇到了一个错误: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue
    
    def stop(self) -> None:
        """停止 agent 循环。"""
        self._running = False
        logger.info("Agent 循环正在停止")
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        处理单条入站消息。
        
        参数:
            msg: 要处理的入站消息。
        
        返回:
            响应消息，如果不需要响应则为 None。
        """
        # 处理系统消息（子 agent 宣告）
        # chat_id 包含原始的 "channel:chat_id"，以便路由回原处
        if msg.channel == "system":
            return await self._process_system_message(msg)
        
        logger.info(f"正在处理来自 {msg.channel}:{msg.sender_id} 的消息")
        
        # 获取或创建会话
        session = self.sessions.get_or_create(msg.session_key)
        
        # 重置验证器状态（新会话开始）
        self.validator.reset()
        # 设置验证上下文（用户请求）
        self.validator.set_context(user_request=msg.content)
        
        # 更新工具上下文
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)
        
        # 语义记忆检索（将用户消息作为 query）
        _semantic_mem = await self.context.fetch_semantic_memory(msg.content)

        # 构建初始消息（使用 get_history 获取 LLM 格式的消息）
        messages = self.context.build_messages(
            history=session.get_history(self.history_window),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            semantic_memory=_semantic_mem,
        )
        
        # Agent 循环 - 添加安全限制
        iteration = 0
        final_content = None
        start_time = time.time()
        total_tokens = 0
        compacted_count = 0  # 已压缩次数
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # 时间检查
            elapsed_time = time.time() - start_time
            if elapsed_time > self.max_total_time:
                final_content = f"处理超时（超过{self.max_total_time // 60}分钟），请简化您的请求或开始新的对话。"
                logger.warning(f"Agent循环超时: {elapsed_time:.1f}秒")
                break
            
            # 调用 LLM 前：主动检测是否需要压缩 (78% 阈值)
            if self.compaction.should_compact(messages, self.max_session_tokens):
                compacted_count += 1
                if compacted_count <= MAX_COMPACTION_ROUNDS:
                    logger.info(
                        f"上下文使用率达到阈值，执行预防性压缩 (第{compacted_count}次)"
                    )
                    messages = await self._compact_context(messages)
                    total_tokens = 0

            # 调用 LLM
            llm_start = time.time()
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            llm_duration_ms = int((time.time() - llm_start) * 1000)
            self._record_usage(
                session_key=msg.session_key,
                model=self.model,
                usage=response.usage,
                duration_ms=llm_duration_ms,
                is_stream=False,
            )
            
            # Token 消耗检查：超限时压缩上下文而非停止
            total_tokens += response.usage.get("total_tokens", 0)
            if total_tokens > self.max_session_tokens:
                compacted_count += 1
                if compacted_count >= MAX_COMPACTION_ROUNDS:
                    # 多次压缩仍超标，强制停止
                    final_content = f"Token消耗过多（{total_tokens}），已多次压缩上下文仍无法控制，请开始新的对话。"
                    logger.warning(f"Token消耗超限且压缩次数用尽: {total_tokens}")
                    break
                logger.info(
                    f"Token累计 {total_tokens}/{self.max_session_tokens} 超限，"
                    f"执行上下文压缩 (第{compacted_count}次)"
                )
                messages = await self._compact_context(messages)
                total_tokens = 0  # 压缩后重置计数
            
            # 处理工具调用
            if response.has_tool_calls:
                # 添加带有工具调用的 assistant 消息
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # 必须是 JSON 字符串
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                # 执行工具
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"正在执行工具：{tool_call.name}，参数：{args_str}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )

                # 工具调用后执行微压缩（大型输出落盘）
                messages = self.compaction.microcompact(messages)
            else:
                # 没有工具调用，验证任务是否真正完成
                should_continue = False
                continuation_prompt = ""
                
                # 1. 检查最小迭代次数
                force_continue, reason = self.validator.should_force_continue(iteration)
                if force_continue:
                    should_continue = True
                    continuation_prompt = f"任务刚开始，请继续调用工具工作。\n原因: {reason}"
                    logger.info(f"迭代次数不足 ({iteration}/{self.validator_config.min_iterations})，强制继续")
                
                # 2. 任务完成验证（仅当最小迭代满足时）
                if not should_continue and self.validator.can_send_continuation_prompt():
                    validation_result = await self.validator.validate(response.content or "")
                    if not validation_result.is_complete:
                        should_continue = True
                        continuation_prompt = validation_result.get_continuation_prompt()
                        self.validator.increment_continuation_count()
                        logger.info(f"任务完成验证未通过: {validation_result.reasons}")
                
                if should_continue:
                    # 注入继续提示，强制 LLM 继续工作
                    messages.append({
                        "role": "user",
                        "content": continuation_prompt
                    })
                    continue
                
                # 验证通过，处理完成
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "我已处理完毕，但没有生成任何响应。"
        
        # 保存到会话
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content
        )
    
    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        处理系统消息（例如子 agent 宣告）。
        
        chat_id 字段包含 "original_channel:original_chat_id"，以便将响应路由回正确的目的地。
        """
        logger.info(f"正在处理来自 {msg.sender_id} 的系统消息")
        
        # 从 chat_id 解析来源（格式："channel:chat_id"）
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # 备选方案
            origin_channel = "cli"
            origin_chat_id = msg.chat_id
        
        # 使用原始会话作为上下文
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        
        # 更新工具上下文
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)
        
        # 语义记忆检索
        _semantic_mem = await self.context.fetch_semantic_memory(msg.content)

        # 使用宣告内容构建消息
        messages = self.context.build_messages(
            history=session.get_history(self.history_window),
            current_message=msg.content,
            semantic_memory=_semantic_mem,
        )
        
        # Agent 循环（针对宣告处理进行了限制）
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            llm_start = time.time()
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            llm_duration_ms = int((time.time() - llm_start) * 1000)
            self._record_usage(
                session_key=session_key,
                model=self.model,
                usage=response.usage,
                duration_ms=llm_duration_ms,
                is_stream=False,
            )
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"正在执行工具：{tool_call.name}，参数：{args_str}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "后台任务已完成。"
        
        # 保存到会话（在历史记录中标记为系统消息）
        session.add_message("user", f"[系统: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )
    
    async def process_direct(self, content: str, session_key: str = "cli:direct") -> str:
        """
        直接处理消息（用于 CLI）。
        
        参数:
            content: 消息内容。
            session_key: 会话标识符。
        
        返回:
            Agent 的响应。
        """
        if ":" in session_key:
            channel, chat_id = session_key.split(":", 1)
        else:
            channel, chat_id = "cli", session_key

        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content
        )
        
        response = await self._process_message(msg)
        return response.content if response else ""

    async def process_direct_stream(
        self,
        content: str,
        session_key: str = "cli:direct",
        on_chunk: Any = None,
        on_trace: Any = None,
        project_info: dict | None = None,
    ) -> str:
        """
        流式直接处理消息，支持实时文本输出和调用链路跟踪。

        Args:
            content: 消息内容。
            session_key: 会话标识符。
            on_chunk: 异步回调 async def on_chunk(text: str)，收到文本片段时调用。
            on_trace: 异步回调 async def on_trace(event: dict)，跟踪事件时调用。
            project_info: 项目信息字典，包含 id, name, path 等。

        Returns:
            Agent 的完整响应文本。
        """
        if ":" in session_key:
            channel, chat_id = session_key.split(":", 1)
        else:
            channel, chat_id = "cli", session_key

        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
        )

        # 记录项目信息
        if project_info:
            logger.info(f"处理项目 '{project_info.get('name')}' 的消息 (路径: {project_info.get('path')})")

        logger.info(f"正在处理来自 {msg.channel}:{msg.sender_id} 的流式消息")

        request_workspace = self._resolve_request_workspace(project_info)
        request_tools = self._build_request_tools(request_workspace)

        session = self.sessions.get_or_create(msg.session_key)

        # 初始化并设置 Harness（长期运行框架）
        from solopreneur.agent.core.harness import LongRunningHarness
        harness = LongRunningHarness(request_workspace)
        self.set_harness(harness)

        # 获取会话上下文（如果已初始化）
        harness_context = None
        if harness.is_initialized():
            harness_context = harness.get_session_context()
            logger.info(f"Harness 已初始化: {harness_context.get('statistics', {})}")

            # effc.md 模式：会话开始时自动运行启动测试（放入线程池，不阻塞 async 事件循环）
            try:
                loop = asyncio.get_event_loop()
                startup_tests = await loop.run_in_executor(
                    None, harness.run_session_startup_tests
                )
                if not startup_tests["passed"]:
                    logger.warning(f"会话启动测试失败: {startup_tests['summary']}")
                else:
                    logger.info(f"会话启动测试通过: {startup_tests['summary']}")
            except Exception as e:
                logger.warning(f"会话启动测试执行异常（不阻塞）: {e}")

        # 更新工具上下文
        message_tool = request_tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)

        spawn_tool = request_tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)

        # 语义记忆检索（含项目级记忆）
        _semantic_mem = await self.context.fetch_semantic_memory(
            msg.content, project_info=project_info
        )

        messages = self.context.build_messages(
            history=session.get_history(self.history_window),
            current_message=msg.content,
            project_info=project_info,
            semantic_memory=_semantic_mem,
        )

        iteration = 0
        start_time = time.time()
        total_tokens = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        compacted_count = 0  # 已压缩次数

        # 累积所有流式输出的文本
        all_streamed: list[str] = []

        async def _emit_trace(event: dict):
            if on_trace:
                await on_trace(event)

        # 将 trace 发射器注入子 Agent 管理器，形成统一调用链
        self.subagents.set_trace_emitter(_emit_trace)

        async def _track_chunk(text: str):
            all_streamed.append(text)
            if on_chunk:
                await on_chunk(text)

        def _make_result_preview(result: Any, max_chars: int = 800) -> str:
            """生成工具输出的可展示预览，避免 UI 过载。"""
            try:
                if isinstance(result, str):
                    text = result
                else:
                    text = json.dumps(result, ensure_ascii=False, default=str)
            except Exception:
                text = str(result)

            text = text.strip()
            if len(text) > max_chars:
                return text[:max_chars] + "\n...<truncated>"
            return text

        def _extract_skill_name(tool_name: str, tool_args: dict[str, Any] | None) -> str | None:
            """识别 read_file 读取 skill 文件的场景，并提取 skill 名称。"""
            if tool_name != "read_file" or not tool_args:
                return None
            path = str(tool_args.get("path") or "")
            if not path:
                return None

            normalized = path.replace("\\", "/")
            match = re.search(r"/skills/([^/]+)/SKILL\.md$", normalized, re.IGNORECASE)
            if not match:
                return None
            return match.group(1)

        # 发送开始事件
        await _emit_trace({
            "event": "start",
            "agent_name": "主控 Agent",
            "model": self.model,
            "session_key": session_key,
            "timestamp": time.time(),
        })

        while iteration < self.max_iterations:
            iteration += 1

            elapsed = time.time() - start_time
            if elapsed > self.max_total_time:
                timeout_msg = f"处理超时（超过{self.max_total_time // 60}分钟），请简化您的请求或开始新的对话。"
                logger.warning(f"Agent循环超时: {elapsed:.1f}秒")
                if on_chunk:
                    await on_chunk(timeout_msg)
                all_streamed.append(timeout_msg)
                break

            # 调用 LLM 前：主动检测是否需要压缩 (78% 阈值)
            if self.compaction.should_compact(messages, self.max_session_tokens):
                compacted_count += 1
                if compacted_count <= MAX_COMPACTION_ROUNDS:
                    logger.info(
                        f"上下文使用率达到阈值，执行预防性压缩 (第{compacted_count}次)"
                    )
                    messages = await self._compact_context(messages)
                    total_tokens = 0
                    await _emit_trace({
                        "event": "compaction",
                        "type": "proactive",
                        "round": compacted_count,
                        "timestamp": time.time(),
                    })

            # 发送 LLM 调用开始事件
            llm_start = time.time()
            await _emit_trace({
                "event": "llm_start",
                "agent_name": "主控 Agent",
                "iteration": iteration,
                "model": self.model,
                "timestamp": llm_start,
            })

            # 使用带重试的 LLM 调用
            try:
                response, call_success = await self._call_llm_with_retry(
                    messages=messages,
                    tools=request_tools.get_definitions(),
                    on_chunk=_track_chunk,
                    use_stream=True,
                )
                llm_duration_ms = int((time.time() - llm_start) * 1000)
                self._record_usage(
                    session_key=msg.session_key,
                    model=self.model,
                    usage=response.usage,
                    duration_ms=llm_duration_ms,
                    is_stream=True,
                )
            except Exception as e:
                # 重试耗尽后的错误处理
                error_msg = f"LLM 调用失败: {type(e).__name__}: {e}"
                logger.error(error_msg)
                if on_chunk:
                    await on_chunk(f"\n\n**[错误]** {error_msg}")
                all_streamed.append(error_msg)
                break

            llm_end = time.time()

            # 获取 token 数据，如果 provider 没有返回则估算
            if response.usage and any(response.usage.values()):
                # Provider 返回了 usage 数据
                prompt_tokens = response.usage.get("prompt_tokens", 0)
                completion_tokens = response.usage.get("completion_tokens", 0)
                step_tokens = response.usage.get("total_tokens", 0)
            else:
                # Provider 没有返回 usage 数据，使用简单估算
                # 假设：中文约 1.5 token/字，英文约 0.25 token/字
                # 这里使用粗略估算：字符数 / 2
                total_chars = sum(len(msg.get("content", "")) for msg in messages)
                output_chars = len("".join(all_streamed)) if all_streamed else 0
                prompt_tokens = total_chars // 2
                completion_tokens = output_chars // 2
                step_tokens = prompt_tokens + completion_tokens
                logger.warning(
                    f"LLM provider did not return usage data, estimating tokens: "
                    f"prompt={prompt_tokens}, completion={completion_tokens}, total={step_tokens}"
                )

            total_tokens += step_tokens
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens

            # 调试日志
            logger.info(f"LLM usage data: {response.usage}, tokens: prompt={prompt_tokens}, completion={completion_tokens}, total={step_tokens}")

            # 发送 LLM 调用结束事件
            await _emit_trace({
                "event": "llm_end",
                "agent_name": "主控 Agent",
                "iteration": iteration,
                "model": self.model,
                "duration_ms": round((llm_end - llm_start) * 1000),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": step_tokens,
                "cumulative_tokens": total_tokens,
                "has_tool_calls": response.has_tool_calls,
                "timestamp": llm_end,
            })

            if total_tokens > self.max_session_tokens:
                compacted_count += 1
                if compacted_count >= MAX_COMPACTION_ROUNDS:
                    warn_msg = f"Token消耗过多（{total_tokens}），已多次压缩上下文仍无法控制，请开始新的对话。"
                    logger.warning(f"Token消耗超限且压缩次数用尽: {total_tokens}")
                    if on_chunk:
                        await on_chunk(warn_msg)
                    all_streamed.append(warn_msg)
                    break
                logger.info(
                    f"Token累计 {total_tokens}/{self.max_session_tokens} 超限，"
                    f"执行上下文压缩 (第{compacted_count}次)"
                )
                messages = await self._compact_context(messages)
                total_tokens = 0  # 压缩后重置计数
                await _emit_trace({
                    "event": "compaction",
                    "type": "reactive",
                    "round": compacted_count,
                    "timestamp": time.time(),
                })

            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )

                for tool_call in response.tool_calls:
                    tool_args = dict(tool_call.arguments or {})
                    if tool_call.name == "run_workflow" and project_info:
                        if not tool_args.get("project_dir") and project_info.get("path"):
                            tool_args["project_dir"] = str(project_info.get("path"))
                        if not tool_args.get("project_name") and project_info.get("name"):
                            tool_args["project_name"] = str(project_info.get("name"))

                    delegate_agent = None
                    if tool_call.name == "delegate":
                        delegate_agent = str(tool_args.get("agent", ""))

                    skill_name = _extract_skill_name(tool_call.name, tool_args)
                    if skill_name:
                        await _emit_trace({
                            "event": "skill_start",
                            "agent_name": "主控 Agent",
                            "iteration": iteration,
                            "skill_name": skill_name,
                            "tool_name": tool_call.name,
                            "tool_args": tool_args,
                            "timestamp": time.time(),
                        })

                    tool_start = time.time()
                    await _emit_trace({
                        "event": "tool_start",
                        "agent_name": "主控 Agent",
                        "iteration": iteration,
                        "tool_name": tool_call.name,
                        "delegate_agent": delegate_agent,
                        "tool_args": tool_args,
                        "timestamp": tool_start,
                    })

                    logger.debug(
                        f"正在执行工具：{tool_call.name}，"
                        f"参数：{json.dumps(tool_args)}"
                    )

                    # ── exec 工具：注入实时流式输出回调 ──────────────────────
                    _exec_tool_for_stream = None
                    if tool_call.name == "exec" and on_chunk is not None:
                        _exec_tool_for_stream = request_tools.get("exec")
                        if _exec_tool_for_stream is not None and hasattr(
                            _exec_tool_for_stream, "set_stream_callback"
                        ):
                            _current_event_loop = asyncio.get_running_loop()

                            def _make_exec_stream_cb(
                                _loop: asyncio.AbstractEventLoop,
                                _on_chunk: Any,
                            ):
                                def _exec_stream_cb(line: str) -> None:
                                    asyncio.run_coroutine_threadsafe(
                                        _on_chunk(line), _loop
                                    )
                                return _exec_stream_cb

                            _exec_tool_for_stream.set_stream_callback(
                                _make_exec_stream_cb(
                                    _current_event_loop, on_chunk
                                )
                            )
                        else:
                            _exec_tool_for_stream = None

                    result = await request_tools.execute(
                        tool_call.name, tool_args
                    )

                    # ── 清除 exec 流式回调 ────────────────────────────────────
                    if _exec_tool_for_stream is not None:
                        _exec_tool_for_stream.set_stream_callback(None)
                    if tool_call.name in {"run_workflow", "delegate", "delegate_parallel", "delegate_auto"}:
                        logger.info(f"请求作用域工作目录: {request_workspace}")
                    tool_end = time.time()
                    await _emit_trace({
                        "event": "tool_end",
                        "agent_name": "主控 Agent",
                        "iteration": iteration,
                        "tool_name": tool_call.name,
                        "delegate_agent": delegate_agent,
                        "duration_ms": round((tool_end - tool_start) * 1000),
                        "result_length": len(str(result)),
                        "result_preview": _make_result_preview(result),
                        "timestamp": tool_end,
                    })

                    if skill_name:
                        await _emit_trace({
                            "event": "skill_end",
                            "agent_name": "主控 Agent",
                            "iteration": iteration,
                            "skill_name": skill_name,
                            "duration_ms": round((tool_end - tool_start) * 1000),
                            "result_length": len(str(result)),
                            "result_preview": _make_result_preview(result),
                            "timestamp": tool_end,
                        })

                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )

                # 工具调用后执行微压缩（大型输出落盘）
                messages = self.compaction.microcompact(messages)
            else:
                # 没有工具调用，验证任务是否真正完成
                should_continue = False
                continuation_prompt = ""

                # 1. 检查最小迭代次数
                force_continue, reason = self.validator.should_force_continue(iteration)
                if force_continue:
                    should_continue = True
                    continuation_prompt = f"任务刚开始，请继续调用工具工作。\n原因: {reason}"
                    logger.info(f"[Stream] 迭代次数不足 ({iteration}/{self.validator_config.min_iterations})，强制继续")

                # 2. 任务完成验证（仅当最小迭代满足时）
                if not should_continue and self.validator.can_send_continuation_prompt():
                    # 收集当前已流式输出的内容用于验证
                    current_content = "".join(all_streamed)
                    validation_result = await self.validator.validate(current_content or response.content or "")
                    if not validation_result.is_complete:
                        should_continue = True
                        continuation_prompt = validation_result.get_continuation_prompt()
                        self.validator.increment_continuation_count()
                        logger.info(f"[Stream] 任务完成验证未通过: {validation_result.reasons}")

                if should_continue:
                    # 注入继续提示，强制 LLM 继续工作
                    messages.append({
                        "role": "user",
                        "content": continuation_prompt
                    })
                    # 通知 UI 任务未完成，继续处理
                    if on_chunk:
                        await on_chunk(f"\n\n---\n**[系统] 任务未完成，继续执行...**\n\n")
                    continue

                # 验证通过，处理完成
                break

        final_content = "".join(all_streamed) if all_streamed else "我已处理完毕，但没有生成任何响应。"

        total_elapsed = time.time() - start_time
        # 发送结束事件
        await _emit_trace({
            "event": "end",
            "agent_name": "主控 Agent",
            "total_iterations": iteration,
            "total_tokens": total_tokens,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_duration_ms": round(total_elapsed * 1000),
            "model": self.model,
            "timestamp": time.time(),
        })

        # 保存到会话
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)

        return final_content
