"""
Delegate 委派工具 - 将任务委派给指定的 Agent。
"""

from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool
from nanobot.agents.registry import AgentRegistry

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager
    from nanobot.agents.manager import AgentManager


class DelegateTool(Tool):
    """
    将任务委派给特定的 Agent 同步执行。

    子 Agent 会执行任务并返回结果，
    主 Agent 可以将结果传递给下一个 Agent。
    """

    def __init__(
        self,
        manager: "SubagentManager",
        agent_manager: "AgentManager",
    ):
        self._manager = manager
        self._agent_manager = agent_manager
        self._registry = AgentRegistry(agent_manager.workspace)

    @property
    def name(self) -> str:
        return "delegate"

    @property
    def description(self) -> str:
        agents_list = ", ".join(
            f"{a.emoji}{a.title}({a.name})" for a in self._registry.list_all()
        )
        return (
            f"将任务委派给特定的 Agent 同步执行。"
            f"可用 Agents: {agents_list}。"
            f"Agent 会完成任务后直接返回结果。"
            f"适用于需要专业分工的复杂任务。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        agent_names = self._registry.get_names()
        return {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "description": "Agent 名称",
                    "enum": agent_names,
                },
                "task": {
                    "type": "string",
                    "description": "要委派给该 Agent 的任务描述",
                },
                "context": {
                    "type": "string",
                    "description": "（可选）前序 Agent 的工作产出或额外上下文，作为该 Agent 工作的输入",
                },
            },
            "required": ["agent", "task"],
        }

    async def execute(
        self,
        agent: str,
        task: str,
        context: str = "",
        **kwargs: Any,
    ) -> str:
        """委派任务给指定 Agent 并同步返回结果。"""
        agent_def = self._agent_manager.get_agent(agent)
        if not agent_def:
            available = ", ".join(self._registry.get_names())
            return f"错误: 未知 Agent '{agent}'。可用 Agents: {available}"

        result = await self._manager.run_with_agent(
            agent_def=agent_def,
            agent_manager=self._agent_manager,
            task=task,
            context=context,
        )

        return f"{agent_def.emoji} **{agent_def.title}** 完成任务\n\n{result}"
