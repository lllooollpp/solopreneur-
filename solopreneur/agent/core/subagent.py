"""用于后台任务执行的子 Agent 管理器。"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any, TYPE_CHECKING

from loguru import logger

from solopreneur.bus.events import InboundMessage
from solopreneur.bus.queue import MessageBus
from solopreneur.providers.base import LLMProvider
from solopreneur.storage import SubagentTaskPersistence, UsagePersistence
from solopreneur.agent.core.tools.registry import ToolRegistry
from solopreneur.agent.core.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from solopreneur.agent.core.tools.db import DBInspectTool
from solopreneur.agent.core.tools.metrics import MetricsInspectTool
from solopreneur.agent.core.tools.repo import GitInspectTool, GitCommandTool, SearchCodeTool
from solopreneur.agent.core.tools.shell import ExecTool
from solopreneur.agent.core.tools.web import WebSearchTool, WebFetchTool

if TYPE_CHECKING:
    from solopreneur.agent.definitions.definition import AgentDefinition
    from solopreneur.agent.definitions.manager import AgentManager


class SubagentManager:
    """
    管理后台子 Agent 的执行。
    
    子 Agent 是轻量级的 Agent 实例，在后台运行以处理特定任务。
    它们共享相同的 LLM 提供者，但拥有隔离的上下文和专注的系统提示词。
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        model: str | None = None,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
    ):
        from solopreneur.config.schema import ExecToolConfig
        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.task_store = SubagentTaskPersistence()
        self.usage_store = UsagePersistence()
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._max_concurrent_subagents = 5  # 最大并发子Agent数
        self._subagent_semaphore = asyncio.Semaphore(self._max_concurrent_subagents)
        self._trace_emitter = None

    def set_trace_emitter(self, emitter) -> None:
        """设置 trace 事件回调（由主 AgentLoop 注入）。"""
        self._trace_emitter = emitter

    async def _emit_trace(self, event: dict[str, Any]) -> None:
        """发送 trace 事件（失败不影响主流程）。"""
        if not self._trace_emitter:
            return
        try:
            await self._trace_emitter(event)
        except Exception as e:
            logger.debug(f"Subagent trace emit failed: {e}")

    def _record_usage(
        self,
        session_key: str,
        usage: dict[str, int] | None,
        duration_ms: int,
    ) -> None:
        """记录一次子 Agent LLM 调用 usage（失败不影响主流程）。"""
        usage = usage or {}
        try:
            self.usage_store.record(
                session_key=session_key,
                model=self.model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                duration_ms=duration_ms,
                is_stream=False,
            )
        except Exception as e:
            logger.warning(f"记录子 Agent LLM usage 失败: {e}")

    def _persist_task(
        self,
        task_id: str,
        label: str,
        task_text: str,
        origin: dict[str, str],
        status: str,
        result_text: str | None = None,
        error_text: str | None = None,
    ) -> None:
        """持久化子任务状态（失败不影响执行流程）。"""
        try:
            self.task_store.upsert(
                task_id=task_id,
                label=label,
                task_text=task_text,
                origin_channel=origin["channel"],
                origin_chat_id=origin["chat_id"],
                status=status,
                result_text=result_text,
                error_text=error_text,
            )
        except Exception as e:
            logger.warning(f"持久化子任务状态失败 [{task_id}] ({status}): {e}")
    
    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
    ) -> str:
        """
        生成一个子 Agent 在后台执行任务。
        
        参数:
            task: 子 Agent 的任务描述。
            label: 可选的人类可读任务标签。
            origin_channel: 结果通知的渠道。
            origin_chat_id: 结果通知的聊天 ID。
        
        返回:
            指示子 Agent 已启动的状态消息。
        """
        # 检查并发限制
        running_count = self.get_running_count()
        if running_count >= self._max_concurrent_subagents:
            return f"无法启动新的子Agent：已达到最大并发数（{self._max_concurrent_subagents}个）。请等待现有任务完成。"
        
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        
        origin = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
        }

        self._persist_task(
            task_id=task_id,
            label=display_label,
            task_text=task,
            origin=origin,
            status="pending",
        )
        
        # 创建后台任务
        bg_task = asyncio.create_task(
            self._run_subagent_with_semaphore(task_id, task, display_label, origin)
        )
        self._running_tasks[task_id] = bg_task
        
        # 完成后清理
        bg_task.add_done_callback(lambda _: self._running_tasks.pop(task_id, None))
        
        logger.info(f"生成子 Agent [{task_id}]: {display_label} (当前运行: {running_count + 1}/{self._max_concurrent_subagents})")
        return f"子 Agent [{display_label}] 已启动 (id: {task_id})。完成后我会通知您。"
    
    async def _run_subagent_with_semaphore(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
    ) -> None:
        """带信号量控制的子Agent执行包装器。"""
        async with self._subagent_semaphore:
            self._persist_task(
                task_id=task_id,
                label=label,
                task_text=task,
                origin=origin,
                status="running",
            )
            await self._run_subagent(task_id, task, label, origin)
    
    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
    ) -> None:
        """执行子 Agent 任务并发布结果。"""
        logger.info(f"子 Agent [{task_id}] 开始执行任务: {label}")
        
        try:
            # 构建子 Agent 工具集（不包含消息工具和生成工具，带工作空间限制）
            tools = ToolRegistry()
            tools.register(ReadFileTool(workspace=self.workspace))
            tools.register(WriteFileTool(workspace=self.workspace))
            tools.register(EditFileTool(workspace=self.workspace))
            tools.register(ListDirTool(workspace=self.workspace))
            tools.register(DBInspectTool())
            tools.register(MetricsInspectTool())
            tools.register(SearchCodeTool(workspace=self.workspace))
            tools.register(GitInspectTool(workspace=self.workspace))
            tools.register(GitCommandTool(workspace=self.workspace))
            tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.exec_config.restrict_to_workspace,
                whitelist_mode=self.exec_config.whitelist_mode,
            ))
            tools.register(WebSearchTool(api_key=self.brave_api_key))
            tools.register(WebFetchTool())
            
            # 构建带有子 Agent 特定提示词的消息列表
            system_prompt = self._build_subagent_prompt(task)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]
            
            # 运行 Agent 循环（限制迭代次数）
            max_iterations = 15
            iteration = 0
            final_result: str | None = None
            
            while iteration < max_iterations:
                iteration += 1

                llm_start = time.time()
                response = await self.provider.chat(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=self.model,
                    max_tokens=16384,
                )
                llm_duration_ms = int((time.time() - llm_start) * 1000)
                self._record_usage(
                    session_key=f"{origin['channel']}:{origin['chat_id']}",
                    usage=response.usage,
                    duration_ms=llm_duration_ms,
                )
                
                if response.has_tool_calls:
                    # 添加带有工具调用的助手消息
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
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": tool_call_dicts,
                    })
                    
                    # 执行工具
                    for tool_call in response.tool_calls:
                        logger.debug(f"子 Agent [{task_id}] 执行工具: {tool_call.name}")
                        result = await tools.execute(tool_call.name, tool_call.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": result,
                        })
                else:
                    final_result = response.content
                    break
            
            if final_result is None:
                final_result = "任务已完成，但未生成最终回复。"
            
            logger.info(f"子 Agent [{task_id}] 执行成功")
            self._persist_task(
                task_id=task_id,
                label=label,
                task_text=task,
                origin=origin,
                status="success",
                result_text=final_result,
            )
            await self._announce_result(task_id, label, task, final_result, origin, "ok")
            
        except Exception as e:
            error_msg = f"错误: {str(e)}"
            logger.error(f"子 Agent [{task_id}] 失败: {e}")
            self._persist_task(
                task_id=task_id,
                label=label,
                task_text=task,
                origin=origin,
                status="failed",
                error_text=error_msg,
            )
            await self._announce_result(task_id, label, task, error_msg, origin, "error")
    
    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
    ) -> None:
        """通过消息总线向主 Agent 宣布子 Agent 的处理结果。"""
        status_text = "已成功完成" if status == "ok" else "执行失败"
        
        announce_content = f"""[子 Agent '{label}' {status_text}]

任务内容: {task}

执行结果:
{result}

请为用户自然地总结此结果。保持简短（1-2 句话）。不要提及“子 Agent”或任务 ID 等技术细节。"""
        
        # 作为系统消息注入，以触发主 Agent
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
        )
        
        await self.bus.publish_inbound(msg)
        logger.debug(f"子 Agent [{task_id}] 已将结果发布到 {origin['channel']}:{origin['chat_id']}")
    
    def _build_subagent_prompt(self, task: str) -> str:
        """为子 Agent 构建专注的系统提示词。"""
        return f"""# 子 Agent

你是主 Agent 生成的子 Agent，用于完成特定的后台任务。

## 你的任务
{task}

## 规则
1. 保持专注 - 仅完成指派的任务，不要做其他事情。
2. 你的最终回复将汇报给主 Agent。
3. 不要主动发起对话或承担额外任务。
4. 汇报发现时要简明扼要。

## 你可以做的
- 在工作空间中读写文件。
- 执行 shell 命令。
- 搜索网页并抓取内容。
- 彻底完成任务。

## 你不可以做的
- 直接发送消息给用户（没有消息工具可用）。
- 生成其他的子 Agent。
- 访问主 Agent 的历史对话记录。

## 工作空间
你的工作空间位于: {self.workspace}

任务完成后，请提供对发现或行动的清晰总结。"""
    
    def get_running_count(self) -> int:
        """返回当前正在运行的子 Agent 数量。"""
        return len(self._running_tasks)

    # ── 角色系统：同步角色执行 ─────────────────────────────────────

    def _build_agent_tools(
        self,
        agent_def: "AgentDefinition",
        project_dir: str = "",
    ) -> ToolRegistry:
        """
        为指定 Agent 构建工具集。

        根据 Agent 的 allowed_tools 过滤可用工具。
        如果 allowed_tools 为 None，则提供全部工具。
        """
        # 兼容性别名
        _build_role_tools = self._build_agent_tools
        # 如果提供了 project_dir，则将工具的 workspace/working_dir 指向该目录，
        # 以便子 Agent 能够在目标项目路径下读写文件。
        workspace_path = Path(project_dir) if project_dir else self.workspace

        all_tools = {
            "read_file": ReadFileTool(workspace=workspace_path),
            "write_file": WriteFileTool(workspace=workspace_path),
            "edit_file": EditFileTool(workspace=workspace_path),
            "list_dir": ListDirTool(workspace=workspace_path),
            "db_inspect": DBInspectTool(),
            "metrics_inspect": MetricsInspectTool(),
            "search_code": SearchCodeTool(workspace=workspace_path),
            "git_inspect": GitInspectTool(workspace=workspace_path),
            "git": GitCommandTool(workspace=workspace_path),
            "exec": ExecTool(
                working_dir=str(workspace_path),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.exec_config.restrict_to_workspace,
                whitelist_mode=self.exec_config.whitelist_mode,
            ),
            "web_search": WebSearchTool(api_key=self.brave_api_key),
            "web_fetch": WebFetchTool(),
        }

        registry = ToolRegistry()

        if agent_def.tools is not None:
            for tool_name in agent_def.tools:
                if tool_name in all_tools:
                    registry.register(all_tools[tool_name])
        else:
            for tool in all_tools.values():
                registry.register(tool)

        return registry

    # 必须调用 write_file 的角色（否则只会输出 MD 描述而不创建文件）
    _MUST_WRITE_ROLES = {"developer", "tester", "devops"}
    # 必须调用 exec 执行测试的角色（防止只输出建议不实际运行测试）
    _MUST_EXEC_ROLES = {"tester"}
    # 必须调用工具（read_file/list_dir/write_file）的角色，避免只输出纯文本
    _MUST_USE_TOOLS_ROLES = {"developer", "tester", "devops", "architect", "code_reviewer"}
    _TOOL_REMINDER_MAX = 3  # 最多提醒几轮使用工具
    _LLM_CALL_MAX_RETRIES = 3  # LLM 调用瞬时错误最大重试次数
    _LLM_CALL_RETRY_BASE_DELAY = 5  # 重试基础延时（秒）

    async def run_with_agents_parallel(
        self,
        agent_manager: "AgentManager",
        jobs: list[dict[str, Any]],
        max_parallel: int = 3,
    ) -> list[dict[str, Any]]:
        """
        并行执行多个 Agent 任务（方案 A：串并行混合）。

        Args:
            agent_manager: Agent 管理器
            jobs: 任务列表，每项格式：
                {"agent": "developer", "task": "...", "context": "", "project_dir": ""}
            max_parallel: 最大并发度（默认 3）

        Returns:
            与 jobs 同序的执行结果列表
        """
        if not jobs:
            return []

        parallel_limit = max(1, min(max_parallel, self._max_concurrent_subagents))
        semaphore = asyncio.Semaphore(parallel_limit)

        results: list[dict[str, Any] | None] = [None] * len(jobs)

        async def _worker(index: int, job: dict[str, Any]) -> None:
            agent_name = str(job.get("agent", "")).strip()
            task = str(job.get("task", "")).strip()
            context = str(job.get("context", ""))
            project_dir = str(job.get("project_dir", ""))

            if not agent_name or not task:
                results[index] = {
                    "ok": False,
                    "agent": agent_name or "",
                    "error": "missing required fields: agent/task",
                }
                return

            agent_def = agent_manager.get_agent(agent_name)
            if not agent_def:
                results[index] = {
                    "ok": False,
                    "agent": agent_name,
                    "error": f"unknown agent: {agent_name}",
                }
                return

            async with semaphore:
                try:
                    output = await self.run_with_agent(
                        agent_def=agent_def,
                        agent_manager=agent_manager,
                        task=task,
                        context=context,
                        project_dir=project_dir,
                    )
                    results[index] = {
                        "ok": True,
                        "agent": agent_name,
                        "title": agent_def.title,
                        "result": output,
                    }
                except Exception as e:
                    results[index] = {
                        "ok": False,
                        "agent": agent_name,
                        "title": agent_def.title,
                        "error": str(e),
                    }

        await asyncio.gather(*[_worker(i, j) for i, j in enumerate(jobs)])
        return [r if r is not None else {"ok": False, "agent": "", "error": "unknown"} for r in results]

    async def run_with_agent(
        self,
        agent_def: "AgentDefinition",
        agent_manager: "AgentManager",
        task: str,
        context: str = "",
        project_dir: str = "",
    ) -> str:
        """
        以指定 Agent 同步执行任务并返回结果。

        与 spawn() 不同，此方法会等待 Agent 完成任务后再返回，
        适用于需要将结果传递给下一个 Agent 的工作流场景。

        Args:
            agent_def: Agent 定义。
            agent_manager: Agent 管理器（用于构建提示词）。
            task: 任务描述。
            context: 前序 Agent 的产出（可选）。
            project_dir: 项目目录路径（可选），用于告知 Agent 代码文件的存放位置。

        Returns:
            Agent 执行的结果文本。
        """
        # 兼容性别名
        run_with_role = self.run_with_agent
        agent_id = f"{agent_def.name}-{str(uuid.uuid4())[:6]}"
        logger.info(
            f"{agent_def.emoji} Agent [{agent_def.title}] ({agent_id}) 开始执行任务"
        )
        await self._emit_trace({
            "event": "agent_start",
            "agent_name": agent_def.name,
            "agent_title": agent_def.title,
            "agent_id": agent_id,
            "timestamp": time.time(),
        })

        logger.debug(
            f"[{agent_id}] 参数: task={task[:100] if task else 'None'}..., "
            f"project_dir={project_dir}, context_len={len(context)}"
        )

        try:
            tools = self._build_agent_tools(agent_def, project_dir=project_dir)
            logger.debug(f"[{agent_id}] 已构建工具集，可用工具: {tools.tool_names}")
        except Exception as e:
            logger.error(f"[{agent_id}] 构建工具集失败: {e}", exc_info=True)
            raise

        # 使用 AgentManager 构建 Agent 专属消息
        logger.debug(f"[{agent_id}] 开始构建消息...")
        messages = agent_manager.build_agent_messages(
            agent=agent_def,
            task=task,
            context=context,
            project_dir=project_dir,
        )
        logger.info(f"[{agent_id}] 已构建 {len(messages)} 条消息")
        # 打印消息摘要（调试用）
        for i, msg in enumerate(messages[:3]):  # 只打印前 3 条
            role = msg.get('role', 'unknown')
            content_preview = (msg.get('content', '') or '')[:100].replace('\n', ' ')
            logger.debug(f"[{agent_id}] 消息 {i+1}: role={role}, content={content_preview}...")

        max_iterations = agent_def.max_iterations
        iteration = 0
        final_result: str | None = None

        # 跟踪工具调用情况 —— 防止 Developer 只描述代码不创建文件
        tools_called: set[str] = set()
        write_file_count = 0
        reminder_count = 0
        must_write = (
            agent_def.name in self._MUST_WRITE_ROLES and bool(project_dir)
        )

        # 子代理也使用微压缩来控制上下文膨胀
        from solopreneur.agent.core.compaction import CompactionEngine
        compactor = CompactionEngine(
            provider=self.provider,
            workspace=self.workspace,
            model=self.model,
        )

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"[{agent_id}] ════════ 迭代 {iteration}/{max_iterations} ════════")

            # 微压缩：大型工具输出落盘
            logger.debug(f"[{agent_id}] 执行微压缩（当前消息数: {len(messages)}）")
            messages = compactor.microcompact(messages)
            logger.debug(f"[{agent_id}] 微压缩完成（当前消息数: {len(messages)}）")

            # LLM 调用（带瞬时错误重试）
            logger.info(f"[{agent_id}] 准备调用 LLM (max_tokens=16384)")
            response = None
            for _retry in range(self._LLM_CALL_MAX_RETRIES):
                try:
                    logger.debug(f"[{agent_id}] 调用 LLM (尝试 {_retry + 1}/{self._LLM_CALL_MAX_RETRIES})")
                    llm_start = time.time()
                    await self._emit_trace({
                        "event": "llm_start",
                        "agent_name": agent_def.name,
                        "iteration": iteration,
                        "model": self.model,
                        "timestamp": llm_start,
                    })
                    response = await self.provider.chat(
                        messages=messages,
                        tools=tools.get_definitions(),
                        model=self.model,
                        max_tokens=16384,  # 代码生成需要更多输出空间
                    )
                    llm_duration_ms = int((time.time() - llm_start) * 1000)
                    self._record_usage(
                        session_key=f"subagent:{agent_id}",
                        usage=response.usage,
                        duration_ms=llm_duration_ms,
                    )
                    logger.info(f"[{agent_id}] ✓ LLM 调用成功 | tool_calls={len(response.tool_calls)} | has_tool_calls={response.has_tool_calls}")
                    await self._emit_trace({
                        "event": "llm_end",
                        "agent_name": agent_def.name,
                        "iteration": iteration,
                        "model": self.model,
                        "duration_ms": llm_duration_ms,
                        "prompt_tokens": (response.usage or {}).get("prompt_tokens", 0),
                        "completion_tokens": (response.usage or {}).get("completion_tokens", 0),
                        "total_tokens": (response.usage or {}).get("total_tokens", 0),
                        "has_tool_calls": response.has_tool_calls,
                        "timestamp": time.time(),
                    })
                    if response.content:
                        content_preview = response.content[:200].replace('\n', ' ')
                        logger.debug(f"[{agent_id}] LLM 回复内容: {content_preview}...")
                    break  # 成功，跳出重试循环
                except Exception as llm_err:
                    retries_left = self._LLM_CALL_MAX_RETRIES - _retry - 1
                    err_desc = f"{type(llm_err).__name__}: {llm_err}" or repr(llm_err)
                    if retries_left > 0:
                        delay = self._LLM_CALL_RETRY_BASE_DELAY * (2 ** _retry)
                        logger.warning(
                            f"{agent_def.emoji} [{agent_id}] LLM 调用失败 ({err_desc}), "
                            f"等待 {delay}s 后重试 (剩余 {retries_left} 次)"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"{agent_def.emoji} [{agent_id}] LLM 调用重试耗尽: {err_desc}"
                        )
                        raise  # 所有重试耗尽，抛出异常

            if response is None:
                # 不应到达这里，但以防万一
                logger.error(f"[{agent_id}] LLM 调用未返回有效响应且未抛出异常")
                raise RuntimeError("LLM 调用未返回有效响应且未抛出异常")

            logger.info(f"[{agent_id}] 处理 LLM 响应...")
            logger.debug(f"[{agent_id}] 响应状态: content_len={len(response.content) if response.content else 0}, tool_calls={len(response.tool_calls) if response.has_tool_calls else 0}")

            if response.has_tool_calls:
                logger.info(f"[{agent_id}] 检测到 {len(response.tool_calls)} 个工具调用")
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
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": tool_call_dicts,
                })

                for tool_call in response.tool_calls:
                    tools_called.add(tool_call.name)
                    if tool_call.name == "write_file":
                        write_file_count += 1
                    tool_start = time.time()
                    await self._emit_trace({
                        "event": "tool_start",
                        "agent_name": agent_def.name,
                        "iteration": iteration,
                        "tool_name": tool_call.name,
                        "tool_args": tool_call.arguments,
                        "timestamp": tool_start,
                    })
                    logger.info(f"[{agent_id}] → 执行工具 [{tool_call.name}]: {json.dumps(tool_call.arguments, ensure_ascii=False)[:150]}...")
                    try:
                        result = await tools.execute(
                            tool_call.name, tool_call.arguments
                        )
                        logger.info(f"[{agent_id}] ✓ 工具 [{tool_call.name}] 执行完成，结果长度: {len(result)}")
                    except Exception as e:
                        logger.error(f"[{agent_id}] ✗ 工具 [{tool_call.name}] 执行失败: {e}", exc_info=True)
                        result = f"Error: {e}"
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": result,
                    })
                    tool_end = time.time()
                    result_text = str(result)
                    await self._emit_trace({
                        "event": "tool_end",
                        "agent_name": agent_def.name,
                        "iteration": iteration,
                        "tool_name": tool_call.name,
                        "duration_ms": int((tool_end - tool_start) * 1000),
                        "result_length": len(result_text),
                        "result_preview": (result_text[:800] + "\n...<truncated>") if len(result_text) > 800 else result_text,
                        "timestamp": tool_end,
                    })
            else:
                logger.info(f"[{agent_id}] LLM 无工具调用，准备结束迭代")
                # ── 工具调用强制保障 ──────────────────────────────
                # 如果角色必须创建文件但还没有调用 write_file，
                # 注入提醒消息要求调用工具而非只描述代码
                if (
                    must_write
                    and "write_file" not in tools_called
                    and reminder_count < self._TOOL_REMINDER_MAX
                ):
                    reminder_count += 1
                    logger.warning(f"[{agent_id}] ⚠️ 角色要求必须写文件但尚未调用 write_file，发送提醒 ({reminder_count}/{self._TOOL_REMINDER_MAX})")
                    # 将模型的文本回复加入上下文
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                    })
                    # 注入强制工具调用提醒
                    messages.append({
                        "role": "user",
                        "content": (
                            "⚠️ 你还没有调用 `write_file` 工具创建任何实际文件！\n\n"
                            "**请停止在文本中描述代码**，你必须立即使用 `write_file` 工具"
                            "将源代码文件写入磁盘。\n\n"
                            f"目标目录：`{project_dir}`\n\n"
                            "请现在开始：\n"
                            "1. 调用 `write_file` 创建第一个源文件\n"
                            "2. 逐个创建所有必要的项目文件\n"
                            "3. 每个文件都必须通过 `write_file` 工具写入\n\n"
                            "不要再解释，直接调用工具。"
                        ),
                    })
                    logger.warning(
                        f"{agent_def.emoji} [{agent_id}] 未调用 write_file，"
                        f"发送提醒 ({reminder_count}/{self._TOOL_REMINDER_MAX})"
                    )
                    continue  # 不退出循环，继续要求模型调用工具

                # ── Tester 角色强制执行测试（exec 保障）──────────
                # 如果 tester 已经写了测试文件但还没有调用 exec 运行测试
                must_exec = (
                    agent_def.name in self._MUST_EXEC_ROLES and bool(project_dir)
                )
                if (
                    must_exec
                    and "exec" not in tools_called
                    and "write_file" in tools_called
                    and reminder_count < self._TOOL_REMINDER_MAX
                ):
                    reminder_count += 1
                    logger.warning(f"[{agent_id}] ⚠️ Tester角色已写测试但未调用exec运行测试 ({reminder_count}/{self._TOOL_REMINDER_MAX})")
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                    })
                    messages.append({
                        "role": "user",
                        "content": (
                            "⚠️ 你已经编写了测试文件，但还没有使用 `exec` 工具实际运行测试！\n\n"
                            "**请停止仅仅描述如何运行测试**，你必须立即使用 `exec` 工具执行测试。\n\n"
                            f"项目目录：`{project_dir}`\n\n"
                            "请现在执行：\n"
                            "1. 使用 `exec` 工具运行你编写的测试\n"
                            "2. 检查测试输出结果\n"
                            "3. 如果测试失败，修复问题并重新运行\n"
                            "4. 只有测试通过后才能报告完成\n\n"
                            "不要再描述命令，直接调用 `exec` 工具运行。"
                        ),
                    })
                    continue

                # 通用工具使用检查：architect/code_reviewer 等角色至少应使用一次工具
                # 如果完全没用过工具就想结束，提醒它先查看项目目录
                if (
                    agent_def.name in self._MUST_USE_TOOLS_ROLES
                    and not tools_called
                    and reminder_count < self._TOOL_REMINDER_MAX
                    and bool(project_dir)
                ):
                    reminder_count += 1
                    logger.warning(f"[{agent_id}] ⚠️ 角色要求必须使用工具但尚未使用任何工具，发送工具使用提醒 ({reminder_count}/{self._TOOL_REMINDER_MAX})")
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                    })
                    messages.append({
                        "role": "user",
                        "content": (
                            "⚠️ 你还没有使用任何工具！\n\n"
                            "你必须先使用 `list_dir` 查看项目目录结构，"
                            "再使用 `read_file` 阅读相关文件，然后基于实际代码给出专业产出。\n\n"
                            f"项目目录：`{project_dir}`\n\n"
                            "请立即调用 `list_dir` 工具开始。不要只在文本中描述你的计划。"
                        ),
                    })
                    logger.warning(
                        f"{agent_def.emoji} [{agent_id}] 未使用任何工具，"
                        f"发送工具使用提醒 ({reminder_count}/{self._TOOL_REMINDER_MAX})"
                    )
                    continue

                final_result = response.content
                logger.info(f"[{agent_id}] 迭代完成，获得最终结果")
                break

        if final_result is None:
            final_result = "任务已完成，但未生成最终回复。"

        # 日志记录工具使用统计
        logger.info(
            f"╔══════════════════════════════════════╗"
        )
        logger.info(
            f"║ {agent_def.emoji} Agent [{agent_def.title}] 完成任务    ║"
        )
        logger.info(
            f"╠──────────────────────────────────────────╢"
        )
        logger.info(
            f"║ Agent ID: {agent_id}                       ║"
        )
        logger.info(
            f"║ 迭代次数: {iteration}/{max_iterations}                   ║"
        )
        logger.info(
            f"║ 写入文件: {write_file_count}                             ║"
        )
        logger.info(
            f"║ 使用工具: {', '.join(sorted(tools_called)) if tools_called else '无'}     ║"
        )
        logger.info(
            f"║ 结果长度: {len(final_result) if final_result else 0} 字符                      ║"
        )
        logger.info(
            f"╚══════════════════════════════════════╝"
        )
        await self._emit_trace({
            "event": "agent_end",
            "agent_name": agent_def.name,
            "agent_title": agent_def.title,
            "agent_id": agent_id,
            "total_iterations": iteration,
            "result_length": len(final_result) if final_result else 0,
            "timestamp": time.time(),
        })
        return final_result
