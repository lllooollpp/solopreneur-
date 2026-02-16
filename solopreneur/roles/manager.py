"""角色管理器 - 加载角色定义，构建角色专属上下文。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from solopreneur.roles.definitions import Role, ROLES, get_role, list_roles

if TYPE_CHECKING:
    from solopreneur.agent.core.skills import SkillsLoader


class RoleManager:
    """
    管理软件工程角色。

    负责加载角色定义、构建角色专属系统提示词、
    组装角色上下文（包括技能内容）。
    """

    def __init__(self, workspace: Path, skills_loader: "SkillsLoader | None" = None):
        self.workspace = workspace
        self._skills_loader = skills_loader

    @property
    def skills(self) -> "SkillsLoader":
        """延迟加载 SkillsLoader 以避免循环依赖。"""
        if self._skills_loader is None:
            from solopreneur.agent.core.skills import SkillsLoader
            self._skills_loader = SkillsLoader(self.workspace)
        return self._skills_loader

    # ── 角色查询 ────────────────────────────────────────────────────

    def get_role(self, name: str) -> Role | None:
        """按名称获取角色。"""
        return get_role(name)

    def list_roles(self) -> list[Role]:
        """列出所有角色。"""
        return list_roles()

    def get_role_names(self) -> list[str]:
        """列出所有角色名称。"""
        return list(ROLES.keys())

    # ── 角色摘要（用于主 Agent 上下文） ────────────────────────────

    def build_roles_summary(self) -> str:
        """
        构建角色摘要，嵌入主 Agent 的系统提示词中。

        让主 Agent（Tech Lead）知道有哪些角色可以委派任务。
        """
        lines = [
            "# 软件工程团队",
            "",
            "你可以使用 `delegate` 工具将任务委派给以下专业角色：",
            "",
        ]

        for role in list_roles():
            lines.append(
                f"- **{role.emoji} {role.title}** (`{role.name}`) - {role.description}"
            )

        lines.extend([
            "",
            "## 执行方式",
            "",
            "收到开发任务后，**立即调用** `run_workflow(mode=\"auto\")` 启动自动流水线。",
            "角色团队会自动协作直到项目完成，你只需在质量不达标时介入。",
            "",
            "**绝不要**停下来问用户确认技术选型——自己做合理默认决策后直接执行。",
        ])

        return "\n".join(lines)

    # ── 角色系统提示词构建 ──────────────────────────────────────────

    def build_role_prompt(
        self, role: Role, task: str, context: str = "", project_dir: str = ""
    ) -> str:
        """
        为指定角色构建完整的系统提示词。

        Args:
            role: 角色定义。
            task: 要执行的任务。
            context: 来自上一步骤的上下文/产出物。
            project_dir: 项目目录路径，告知角色代码文件的存放位置。

        Returns:
            完整的系统提示词。
        """
        parts = [role.system_prompt]

        # 加载角色专属技能
        if role.skills:
            skill_content = self.skills.load_skills_for_context(list(role.skills))
            if skill_content:
                parts.append(f"\n\n# 参考技能\n\n{skill_content}")

        # 工作空间信息
        workspace_path = str(self.workspace.expanduser().resolve())
        parts.append(f"\n\n# 工作空间\n\n你的工作空间位于: {workspace_path}")

        # 项目目录信息（关键：告知角色代码的存放位置）
        if project_dir:
            parts.append(
                f"\n\n# 项目目录\n\n"
                f"所有代码文件必须创建在: {project_dir}\n\n"
                f"**重要规则：**\n"
                f"- 使用 `write_file` 工具时，文件路径必须以此目录开头\n"
                f"- 你必须创建实际的源代码文件，而不是仅在文本中描述代码\n"
                f"- 每个源代码文件都必须通过 `write_file` 工具写入磁盘\n"
                f"- 禁止仅输出代码片段而不调用 `write_file` 创建文件"
            )

        # 上游上下文
        if context:
            parts.append(f"\n\n# 上游工作成果\n\n以下是前序角色的工作产出，请基于此继续工作：\n\n{context}")

        # 输出格式要求
        if role.output_format:
            parts.append(f"\n\n# 输出格式\n\n{role.output_format}")

        # 任务提示
        parts.append(
            f"\n\n# 当前任务\n\n请以 **{role.title}** 的身份完成以下任务：\n\n{task}"
        )

        return "\n".join(parts)

    def build_role_messages(
        self,
        role: Role,
        task: str,
        context: str = "",
        project_dir: str = "",
    ) -> list[dict[str, Any]]:
        """
        为指定角色构建完整的消息列表。

        Args:
            role: 角色定义。
            task: 要执行的任务。
            context: 前序工作产出。
            project_dir: 项目目录路径。

        Returns:
            LLM 消息列表。
        """
        system_prompt = self.build_role_prompt(role, task, context, project_dir)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        return messages
