"""用于后台任务执行的子 Agent 管理器。"""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, TYPE_CHECKING

from loguru import logger

from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool

if TYPE_CHECKING:
    from nanobot.agents.definition import AgentDefinition
    from nanobot.agents.manager import AgentManager


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
        from nanobot.config.schema import ExecToolConfig
        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._max_concurrent_subagents = 5  # 最大并发子Agent数
        self._subagent_semaphore = asyncio.Semaphore(self._max_concurrent_subagents)
    
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
            tools.register(ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.exec_config.restrict_to_workspace,
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
                
                response = await self.provider.chat(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=self.model,
                    max_tokens=16384,
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
            await self._announce_result(task_id, label, task, final_result, origin, "ok")
            
        except Exception as e:
            error_msg = f"错误: {str(e)}"
            logger.error(f"子 Agent [{task_id}] 失败: {e}")
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
    ) -> ToolRegistry:
        """
        为指定 Agent 构建工具集。

        根据 Agent 的 allowed_tools 过滤可用工具。
        如果 allowed_tools 为 None，则提供全部工具。
        """
        # 兼容性别名
        _build_role_tools = self._build_agent_tools
        all_tools = {
            "read_file": ReadFileTool(workspace=self.workspace),
            "write_file": WriteFileTool(workspace=self.workspace),
            "edit_file": EditFileTool(workspace=self.workspace),
            "list_dir": ListDirTool(workspace=self.workspace),
            "exec": ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.exec_config.restrict_to_workspace,
            ),
            "web_search": WebSearchTool(api_key=self.brave_api_key),
            "web_fetch": WebFetchTool(),
        }

        registry = ToolRegistry()

        if role_def.allowed_tools is not None:
            for tool_name in role_def.allowed_tools:
                if tool_name in all_tools:
                    registry.register(all_tools[tool_name])
        else:
            for tool in all_tools.values():
                registry.register(tool)

        return registry

    # 必须调用 write_file 的角色（否则只会输出 MD 描述而不创建文件）
    _MUST_WRITE_ROLES = {"developer", "tester", "devops"}
    # 必须调用工具（read_file/list_dir/write_file）的角色，避免只输出纯文本
    _MUST_USE_TOOLS_ROLES = {"developer", "tester", "devops", "architect", "code_reviewer"}
    _TOOL_REMINDER_MAX = 3  # 最多提醒几轮使用工具
    _LLM_CALL_MAX_RETRIES = 3  # LLM 调用瞬时错误最大重试次数
    _LLM_CALL_RETRY_BASE_DELAY = 5  # 重试基础延时（秒）

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

        tools = self._build_agent_tools(agent_def)

        # 使用 AgentManager 构建 Agent 专属消息
        messages = agent_manager.build_agent_messages(
            agent=agent_def,
            task=task,
            context=context,
            project_dir=project_dir,
        )

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
        from nanobot.agent.compaction import CompactionEngine
        compactor = CompactionEngine(
            provider=self.provider,
            workspace=self.workspace,
            model=self.model,
        )

        while iteration < max_iterations:
            iteration += 1

            # 微压缩：大型工具输出落盘
            messages = compactor.microcompact(messages)

            # LLM 调用（带瞬时错误重试）
            response = None
            for _retry in range(self._LLM_CALL_MAX_RETRIES):
                try:
                    response = await self.provider.chat(
                        messages=messages,
                        tools=tools.get_definitions(),
                        model=self.model,
                        max_tokens=16384,  # 代码生成需要更多输出空间
                    )
                    break  # 成功，跳出重试循环
                except Exception as llm_err:
                    retries_left = self._LLM_CALL_MAX_RETRIES - _retry - 1
                    err_desc = f"{type(llm_err).__name__}: {llm_err}" or repr(llm_err)
                    if retries_left > 0:
                        delay = self._LLM_CALL_RETRY_BASE_DELAY * (2 ** _retry)
                        logger.warning(
                            f"{role_def.emoji} [{role_id}] LLM 调用失败 ({err_desc}), "
                            f"等待 {delay}s 后重试 (剩余 {retries_left} 次)"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"{role_def.emoji} [{role_id}] LLM 调用重试耗尽: {err_desc}"
                        )
                        raise  # 所有重试耗尽，抛出异常

            if response is None:
                # 不应到达这里，但以防万一
                raise RuntimeError("LLM 调用未返回有效响应且未抛出异常")

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
                messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": tool_call_dicts,
                })

                for tool_call in response.tool_calls:
                    tools_called.add(tool_call.name)
                    if tool_call.name == "write_file":
                        write_file_count += 1
                    logger.debug(
                        f"{agent_def.emoji} [{agent_id}] 执行工具: {tool_call.name}"
                    )
                    result = await tools.execute(
                        tool_call.name, tool_call.arguments
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": result,
                    })
            else:
                # ── 工具调用强制保障 ──────────────────────────────
                # 如果角色必须创建文件但还没有调用 write_file，
                # 注入提醒消息要求调用工具而非只描述代码
                if (
                    must_write
                    and "write_file" not in tools_called
                    and reminder_count < self._TOOL_REMINDER_MAX
                ):
                    reminder_count += 1
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

                # 通用工具使用检查：architect/code_reviewer 等角色至少应使用一次工具
                # 如果完全没用过工具就想结束，提醒它先查看项目目录
                if (
                    agent_def.name in self._MUST_USE_TOOLS_ROLES
                    and not tools_called
                    and reminder_count < self._TOOL_REMINDER_MAX
                    and bool(project_dir)
                ):
                    reminder_count += 1
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
                break

        if final_result is None:
            final_result = "任务已完成，但未生成最终回复。"

        # 日志记录工具使用统计
        logger.info(
            f"{role_def.emoji} 角色 [{role_def.title}] ({role_id}) 完成任务 "
            f"(迭代 {iteration}/{max_iterations}, "
            f"write_file={write_file_count}, "
            f"tools={tools_called or '无'})"
        )
        return final_result
