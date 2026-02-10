"""Agent 循环：核心处理引擎。"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.context import ContextBuilder
from nanobot.agent.compaction import CompactionEngine
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.subagent import SubagentManager
from nanobot.session.manager import SessionManager

# 安全限制常量（默认值，可通过 config 覆盖）
DEFAULT_MAX_TOTAL_TIME = 1800  # 30分钟总时间限制
DEFAULT_MAX_TOKENS_PER_SESSION = 500000  # 每次会话最大Token数
# 自动压缩最大次数
MAX_COMPACTION_ROUNDS = 10


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
        max_iterations: int = 20,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        max_session_tokens: int = 0,
        max_total_time: int = 0,
    ):
        from nanobot.config.schema import ExecToolConfig
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.max_session_tokens = max_session_tokens or DEFAULT_MAX_TOKENS_PER_SESSION
        self.max_total_time = max_total_time or DEFAULT_MAX_TOTAL_TIME
        
        self.context = ContextBuilder(workspace)
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

        # 三层压缩引擎
        self.compaction = CompactionEngine(
            provider=provider,
            workspace=workspace,
            model=self.model,
        )

        # 延迟导入以避免循环依赖
        from nanobot.agents.manager import AgentManager
        from nanobot.workflow.engine import WorkflowEngine

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
    
    def _register_default_tools(self) -> None:
        """注册默认工具集。"""
        # 文件工具（带工作空间限制）
        self.tools.register(ReadFileTool(workspace=self.workspace))
        self.tools.register(WriteFileTool(workspace=self.workspace))
        self.tools.register(EditFileTool(workspace=self.workspace))
        self.tools.register(ListDirTool(workspace=self.workspace))
        
        # Shell 工具
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.exec_config.restrict_to_workspace,
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
        from nanobot.agent.tools.delegate import DelegateTool
        delegate_tool = DelegateTool(
            manager=self.subagents,
            role_manager=self.role_manager,
        )
        self.tools.register(delegate_tool)
        
        # 工作流工具 (run_workflow，用于执行预定义的开发流水线)
        from nanobot.workflow.engine import RunWorkflowTool, WorkflowControlTool
        workflow_tool = RunWorkflowTool(engine=self.workflow_engine)
        self.tools.register(workflow_tool)
        
        control_tool = WorkflowControlTool(engine=self.workflow_engine)
        self.tools.register(control_tool)

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
        
        # 更新工具上下文
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)
        
        # 构建初始消息（使用 get_history 获取 LLM 格式的消息）
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
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
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
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
                # 没有工具调用，处理完成
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
        
        # 使用宣告内容构建消息
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content
        )
        
        # Agent 循环（针对宣告处理进行了限制）
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
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
    ) -> str:
        """
        流式直接处理消息，支持实时文本输出和调用链路跟踪。

        Args:
            content: 消息内容。
            session_key: 会话标识符。
            on_chunk: 异步回调 async def on_chunk(text: str)，收到文本片段时调用。
            on_trace: 异步回调 async def on_trace(event: dict)，跟踪事件时调用。

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

        logger.info(f"正在处理来自 {msg.channel}:{msg.sender_id} 的流式消息")

        session = self.sessions.get_or_create(msg.session_key)

        # 更新工具上下文
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)

        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)

        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
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

        async def _track_chunk(text: str):
            all_streamed.append(text)
            if on_chunk:
                await on_chunk(text)

        # 发送开始事件
        await _emit_trace({
            "event": "start",
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
                "iteration": iteration,
                "model": self.model,
                "timestamp": llm_start,
            })

            # 优先使用流式调用
            if hasattr(self.provider, "chat_stream"):
                response = await self.provider.chat_stream(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    model=self.model,
                    on_chunk=_track_chunk,
                )
            else:
                # 回退到非流式
                response = await self.provider.chat(
                    messages=messages,
                    tools=self.tools.get_definitions(),
                    model=self.model,
                )
                # 非流式时手动发送文本
                if response.content and not response.has_tool_calls and on_chunk:
                    await _track_chunk(response.content)

            llm_end = time.time()
            prompt_tokens = response.usage.get("prompt_tokens", 0)
            completion_tokens = response.usage.get("completion_tokens", 0)
            step_tokens = response.usage.get("total_tokens", 0)
            total_tokens += step_tokens
            total_prompt_tokens += prompt_tokens
            total_completion_tokens += completion_tokens

            # 发送 LLM 调用结束事件
            await _emit_trace({
                "event": "llm_end",
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
                    tool_start = time.time()
                    await _emit_trace({
                        "event": "tool_start",
                        "iteration": iteration,
                        "tool_name": tool_call.name,
                        "tool_args": tool_call.arguments,
                        "timestamp": tool_start,
                    })

                    logger.debug(
                        f"正在执行工具：{tool_call.name}，"
                        f"参数：{json.dumps(tool_call.arguments)}"
                    )
                    result = await self.tools.execute(
                        tool_call.name, tool_call.arguments
                    )

                    tool_end = time.time()
                    await _emit_trace({
                        "event": "tool_end",
                        "iteration": iteration,
                        "tool_name": tool_call.name,
                        "duration_ms": round((tool_end - tool_start) * 1000),
                        "result_length": len(str(result)),
                        "timestamp": tool_end,
                    })

                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )

                # 工具调用后执行微压缩（大型输出落盘）
                messages = self.compaction.microcompact(messages)
            else:
                break

        final_content = "".join(all_streamed) if all_streamed else "我已处理完毕，但没有生成任何响应。"

        total_elapsed = time.time() - start_time
        # 发送结束事件
        await _emit_trace({
            "event": "end",
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
