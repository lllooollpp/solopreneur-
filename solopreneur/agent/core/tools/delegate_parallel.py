"""
Delegate Parallel 工具 - 并行委派多个 Agent 任务。
"""

from typing import Any, TYPE_CHECKING

from solopreneur.agent.core.tools.base import Tool

if TYPE_CHECKING:
    from solopreneur.agent.core.subagent import SubagentManager
    from solopreneur.agent.definitions.manager import AgentManager


class DelegateParallelTool(Tool):
    """将多个任务并行委派给不同 Agent，并聚合返回结果。"""

    def __init__(
        self,
        manager: "SubagentManager",
        agent_manager: "AgentManager",
    ):
        self._manager = manager
        self._agent_manager = agent_manager

    @property
    def name(self) -> str:
        return "delegate_parallel"

    @property
    def description(self) -> str:
        return (
            "并行委派多个独立任务给不同 Agent。"
            "适合低耦合任务（如前后端脚手架、文档、测试样例）并行加速。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        agent_names = self._agent_manager.get_agent_names()
        return {
            "type": "object",
            "properties": {
                "jobs": {
                    "type": "array",
                    "description": "并行任务列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent": {
                                "type": "string",
                                "description": "Agent 名称",
                                "enum": agent_names,
                            },
                            "task": {
                                "type": "string",
                                "description": "委派给该 Agent 的任务",
                            },
                            "context": {
                                "type": "string",
                                "description": "可选上下文",
                            },
                            "project_dir": {
                                "type": "string",
                                "description": "可选项目目录",
                            },
                        },
                        "required": ["agent", "task"],
                    },
                },
                "max_parallel": {
                    "type": "integer",
                    "description": "最大并发数（默认 3）",
                    "minimum": 1,
                    "maximum": 8,
                },
            },
            "required": ["jobs"],
        }

    async def execute(
        self,
        jobs: list[dict[str, Any]],
        max_parallel: int = 3,
        **kwargs: Any,
    ) -> str:
        if not jobs:
            return "错误: jobs 不能为空"

        results = await self._manager.run_with_agents_parallel(
            agent_manager=self._agent_manager,
            jobs=jobs,
            max_parallel=max_parallel,
        )

        ok_count = sum(1 for r in results if r.get("ok"))
        fail_count = len(results) - ok_count

        lines = [
            f"并行委派完成：成功 {ok_count} / 失败 {fail_count}",
            "",
        ]

        for idx, r in enumerate(results, 1):
            agent = r.get("agent", "unknown")
            title = r.get("title", agent)
            if r.get("ok"):
                lines.append(f"## [{idx}] ✅ {title} ({agent})")
                lines.append(r.get("result", ""))
            else:
                lines.append(f"## [{idx}] ❌ {title} ({agent})")
                lines.append(f"错误: {r.get('error', 'unknown error')}")
            lines.append("")

        return "\n".join(lines)
