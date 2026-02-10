"""Delegate 委派工具 - 将任务委派给指定的软件工程角色。"""

from typing import Any, TYPE_CHECKING

from nanobot.agent.tools.base import Tool
from nanobot.roles.definitions import ROLES

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager
    from nanobot.roles.manager import RoleManager


class DelegateTool(Tool):
    """
    将任务委派给特定的软件工程角色。

    角色子代理会同步执行任务并返回结果，
    主 Agent（Tech Lead）可以将结果传递给下一个角色。
    """

    def __init__(
        self,
        manager: "SubagentManager",
        role_manager: "RoleManager",
    ):
        self._manager = manager
        self._role_manager = role_manager

    @property
    def name(self) -> str:
        return "delegate"

    @property
    def description(self) -> str:
        roles_list = ", ".join(
            f"{r.emoji}{r.title}({r.name})" for r in ROLES.values()
        )
        return (
            f"将任务委派给软件工程团队中的特定角色同步执行。"
            f"可用角色: {roles_list}。"
            f"角色会完成任务后直接返回结果。"
            f"适用于需要专业分工的软件开发任务。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "description": "角色名称",
                    "enum": list(ROLES.keys()),
                },
                "task": {
                    "type": "string",
                    "description": "要委派给该角色的任务描述",
                },
                "context": {
                    "type": "string",
                    "description": "（可选）前序角色的工作产出或额外上下文，作为该角色工作的输入",
                },
            },
            "required": ["role", "task"],
        }

    async def execute(
        self,
        role: str,
        task: str,
        context: str = "",
        **kwargs: Any,
    ) -> str:
        """委派任务给指定角色并同步返回结果。"""
        role_def = self._role_manager.get_role(role)
        if not role_def:
            available = ", ".join(ROLES.keys())
            return f"错误: 未知角色 '{role}'。可用角色: {available}"

        result = await self._manager.run_with_role(
            role_def=role_def,
            role_manager=self._role_manager,
            task=task,
            context=context,
        )

        return f"{role_def.emoji} **{role_def.title}** 完成任务\n\n{result}"
