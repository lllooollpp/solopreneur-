"""
Delegate 委派工具 - 将任务委派给指定�?Agent�?
"""

from typing import Any, TYPE_CHECKING

from solopreneur.agent.core.tools.base import Tool
from solopreneur.agent.definitions.registry import AgentRegistry

if TYPE_CHECKING:
    from solopreneur.agent.core.subagent import SubagentManager
    from solopreneur.agent.definitions.manager import AgentManager


class DelegateTool(Tool):
    """
    将任务委派给特定�?Agent 同步执行�?

    �?Agent 会执行任务并返回结果�?
    �?Agent 可以将结果传递给下一�?Agent�?
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
            f"将任务委派给特定�?Agent 同步执行�?
            f"可用 Agents: {agents_list}�?
            f"Agent 会完成任务后直接返回结果�?
            f"适用于需要专业分工的复杂任务�?
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
                    "description": "要委派给�?Agent 的任务描�?,
                },
                "context": {
                    "type": "string",
                    "description": "（可选）前序 Agent 的工作产出或额外上下文，作为�?Agent 工作的输�?,
                },
                "project_dir": {
                    "type": "string",
                    "description": "（可选）项目目录路径，Agent 生成的文件将写入此目�?,
                },
            },
            "required": ["agent", "task"],
        }

    async def execute(
        self,
        agent: str,
        task: str,
        context: str = "",
        project_dir: str = "",
        **kwargs: Any,
    ) -> str:
        """委派任务给指�?Agent 并同步返回结果�?""
        agent_def = self._agent_manager.get_agent(agent)
        if not agent_def:
            available = ", ".join(self._registry.get_names())
            return f"错误: 未知 Agent '{agent}'。可�?Agents: {available}"

        result = await self._manager.run_with_agent(
            agent_def=agent_def,
            agent_manager=self._agent_manager,
            task=task,
            context=context,
            project_dir=project_dir,
        )

        return f"{agent_def.emoji} **{agent_def.title}** 完成任务\n\n{result}"
