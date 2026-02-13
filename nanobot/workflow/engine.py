"""工作流引擎 - 编排多Agent协作的开发流水线，支持自动/分步/混合模式。"""

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from nanobot.agent.core.subagent import SubagentManager
    from nanobot.agent.definitions.manager import AgentManager

from nanobot.agent.core.tools.base import Tool


@dataclass
class WorkflowStep:
    """工作流的一个步骤。"""

    agent: str  # 执行该步骤的 Agent 名称（原 role）
    
    # 兼容性属性，role 别名指向 agent
    @property
    def role(self) -> str:
        return self.agent
    task_template: str  # 任务描述模板，可包含 {description} 和 {prev_output} 占位符
    label: str  # 步骤标签
    save_as: str = ""  # 输出保存的文件名（相对于项目目录），留空不保存


@dataclass
class Workflow:
    """预定义的开发工作流。"""

    name: str  # 工作流标识
    title: str  # 显示名称
    description: str  # 工作流描述
    steps: list[WorkflowStep] = field(default_factory=list)


@dataclass
class WorkflowSession:
    """分步工作流会话，跟踪执行进度。"""

    session_id: str
    workflow: Workflow
    description: str
    project_name: str
    current_step: int = 0  # 下一个待执行的步骤索引 (0-based)
    step_outputs: list[str] = field(default_factory=list)  # 每步的输出
    step_statuses: list[str] = field(default_factory=list)  # "success" | "error" | "skipped" | "injected"
    started_at: float = 0.0
    finished: bool = False

    @property
    def total_steps(self) -> int:
        return len(self.workflow.steps)

    @property
    def prev_output(self) -> str:
        """最近一步的有效输出。"""
        for output in reversed(self.step_outputs):
            if output:
                return output
        return ""

    @property
    def is_complete(self) -> bool:
        return self.current_step >= self.total_steps or self.finished

    def status_summary(self) -> str:
        """返回会话状态摘要。"""
        lines = [
            f"📦 **工作流**: {self.workflow.title} (`{self.workflow.name}`)",
            f"🆔 **会话**: `{self.session_id}`",
            f"📝 **任务**: {self.description}",
            f"📊 **进度**: {self.current_step}/{self.total_steps} 步",
        ]
        # 已完成步骤
        for i, step in enumerate(self.workflow.steps):
            if i < len(self.step_statuses):
                emoji = {"success": "✅", "error": "❌", "skipped": "⏭️", "injected": "📌"}.get(
                    self.step_statuses[i], "❓"
                )
                lines.append(f"  {emoji} 步骤 {i + 1}: {step.label} ({step.agent})")
            elif i == self.current_step:
                lines.append(f"  ▶️ 步骤 {i + 1}: {step.label} ({step.agent}) — **当前待办**")
            else:
                lines.append(f"  ⬜ 步骤 {i + 1}: {step.label} ({step.agent})")
        
        if self.finished:
            lines.append("\n🏁 **状态**: 已完成")
        else:
            next_step = self.workflow.steps[self.current_step]
            lines.append(f"\n💡 **Tech Lead 建议操作**:")
            lines.append(f"1. 审查上述产出。")
            lines.append(f"2. 如果满意，继续执行: `workflow_control(session_id=\"{self.session_id}\", command=\"next\")`。")
            lines.append(f"3. 如果需要修改，可以使用 `delegate` 重做或 `workflow_control(..., command=\"inject\")` 注入修正。")
            
        return "\n".join(lines)


# ── 预定义工作流 ──────────────────────────────────────────────────────

FEATURE_WORKFLOW = Workflow(
    name="feature",
    title="功能开发",
    description="完整的功能开发流程：需求分析 → 架构设计 → 编码实现 → 代码审查 → 测试",
    steps=[
        WorkflowStep(
            agent="product_manager",
            label="需求分析",
            task_template=(
                "分析以下功能需求，输出产品需求文档（PRD）。\n"
                "项目名称: 项目将保存到 `{project_dir}`\n\n{description}"
            ),
            save_as="docs/requirements.md",
        ),
        WorkflowStep(
            agent="architect",
            label="架构设计",
            task_template=(
                "基于以下需求文档，设计技术方案。\n"
                "项目目录: `{project_dir}`\n\n"
                "# 原始需求\n{description}\n\n"
                "# 产品需求文档\n{prev_output}"
            ),
            save_as="docs/architecture.md",
        ),
        WorkflowStep(
            agent="developer",
            label="编码实现",
            task_template=(
                "根据以下技术设计方案进行编码实现。\n\n"
                "## 重要：项目目录\n"
                "所有代码文件必须创建在项目目录下：`{project_dir}`\n"
                "你必须使用 `write_file` 工具在该目录下创建实际的源代码文件（.py, .js, .html, .css 等），"
                "而不是仅仅描述代码内容。\n"
                "请先用 `list_dir` 查看项目目录结构，然后创建必要的文件。\n\n"
                "## 必须完成的操作\n"
                "1. 在 `{project_dir}` 下创建完整的项目结构（目录和文件）\n"
                "2. 使用 `write_file` 写入每个源代码文件的完整内容\n"
                "3. 如需安装依赖，使用 `exec` 工具执行安装命令\n"
                "4. 最后输出创建的文件清单\n\n"
                "# 原始需求\n{description}\n\n"
                "# 技术设计\n{prev_output}"
            ),
        ),
        WorkflowStep(
            agent="code_reviewer",
            label="代码审查",
            task_template=(
                "审查本次功能开发的代码变更。\n"
                "项目目录: `{project_dir}`\n"
                "请使用 `list_dir` 和 `read_file` 查看项目实际代码文件进行审查。\n\n"
                "# 功能描述\n{description}\n\n"
                "# 开发者报告\n{prev_output}"
            ),
            save_as="docs/review.md",
        ),
        WorkflowStep(
            agent="security_engineer",
            label="安全审查",
            task_template=(
                "基于当前实现进行应用安全审查并给出可执行修复建议。\n"
                "项目目录: `{project_dir}`\n"
                "请使用 `list_dir` / `read_file` 进行证据化审查。\n\n"
                "# 功能描述\n{description}\n\n"
                "# 代码审查结果\n{prev_output}"
            ),
            save_as="docs/security-review.md",
        ),
        WorkflowStep(
            agent="tester",
            label="测试",
            task_template=(
                "为以下功能编写和执行测试。\n"
                "项目目录: `{project_dir}`\n"
                "请使用 `write_file` 在项目目录下创建测试文件，"
                "并使用 `exec` 运行测试。\n\n"
                "# 功能描述\n{description}\n\n"
                "# 安全审查与代码审查反馈\n{prev_output}"
            ),
        ),
    ],
)

BUGFIX_WORKFLOW = Workflow(
    name="bugfix",
    title="Bug 修复",
    description="Bug 修复流程：问题分析 → 修复实现 → 代码审查 → 测试验证",
    steps=[
        WorkflowStep(
            agent="developer",
            label="问题分析与修复",
            task_template=(
                "分析并修复以下 Bug。\n"
                "项目目录: `{project_dir}`\n"
                "请使用 `list_dir` 和 `read_file` 查看代码，"
                "使用 `write_file` 或 `edit_file` 修复问题。\n\n{description}"
            ),
        ),
        WorkflowStep(
            agent="code_reviewer",
            label="修复审查",
            task_template=(
                "审查以下 Bug 修复的代码变更。\n"
                "项目目录: `{project_dir}`\n\n"
                "# Bug 描述\n{description}\n\n"
                "# 修复报告\n{prev_output}"
            ),
            save_as="docs/bugfix-review.md",
        ),
        WorkflowStep(
            agent="tester",
            label="回归测试",
            task_template=(
                "针对以下 Bug 修复编写回归测试并执行。\n"
                "项目目录: `{project_dir}`\n\n"
                "# Bug 描述\n{description}\n\n"
                "# 修复与审查\n{prev_output}"
            ),
        ),
    ],
)

REVIEW_WORKFLOW = Workflow(
    name="review",
    title="代码审查",
    description="独立代码审查流程：审查代码 → 安全检查 → 测试补充建议",
    steps=[
        WorkflowStep(
            agent="code_reviewer",
            label="代码审查",
            task_template=(
                "审查以下代码或变更。\n"
                "项目目录: `{project_dir}`\n\n{description}"
            ),
            save_as="docs/review.md",
        ),
        WorkflowStep(
            agent="tester",
            label="测试建议",
            task_template=(
                "根据代码审查结果建议需要补充的测试。\n"
                "项目目录: `{project_dir}`\n\n"
                "# 审查内容\n{description}\n\n"
                "# 审查结果\n{prev_output}"
            ),
        ),
    ],
)

DEPLOY_WORKFLOW = Workflow(
    name="deploy",
    title="部署上线",
    description="部署流程：测试验证 → 部署配置 → 上线",
    steps=[
        WorkflowStep(
            agent="tester",
            label="部署前测试",
            task_template=(
                "执行部署前的完整测试验证。\n"
                "项目目录: `{project_dir}`\n\n{description}"
            ),
        ),
        WorkflowStep(
            agent="release_manager",
            label="发布准备",
            task_template=(
                "准备发布清单与上线回滚方案。\n"
                "项目目录: `{project_dir}`\n\n"
                "# 发布目标\n{description}\n\n"
                "# 测试结果\n{prev_output}"
            ),
            save_as="docs/release-plan.md",
        ),
        WorkflowStep(
            agent="devops",
            label="部署配置与执行",
            task_template=(
                "配置并执行部署。\n"
                "项目目录: `{project_dir}`\n\n"
                "# 部署需求\n{description}\n\n"
                "# 发布准备\n{prev_output}"
            ),
            save_as="docs/deployment.md",
        ),
        WorkflowStep(
            agent="sre_engineer",
            label="发布后验证",
            task_template=(
                "执行发布后稳定性验证与可观测性检查。\n"
                "项目目录: `{project_dir}`\n"
                "请输出告警、SLO 与回归风险结论。\n\n"
                "# 发布信息\n{description}\n\n"
                "# 部署结果\n{prev_output}"
            ),
            save_as="docs/post-deploy-validation.md",
        ),
    ],
)

# 工作流注册表
WORKFLOWS: dict[str, Workflow] = {
    w.name: w
    for w in (FEATURE_WORKFLOW, BUGFIX_WORKFLOW, REVIEW_WORKFLOW, DEPLOY_WORKFLOW)
}


# ── 工作流引擎 ───────────────────────────────────────────────────────


class WorkflowEngine:
    """
    执行预定义的开发工作流。

    逐步调用不同Agent的子 Agent，将每步产出传递给下一步，
    并保存中间产物到项目目录。
    支持自动流水线模式和分步交互模式。
    """

    def __init__(
        self,
        subagent_manager: "SubagentManager",
        agent_manager: "AgentManager",
        workspace: Path,
    ):
        self.subagent_manager = subagent_manager
        self.agent_manager = agent_manager
        self.workspace = workspace
        self.sessions: dict[str, WorkflowSession] = {}

    def get_session(self, session_id: str) -> WorkflowSession | None:
        return self.sessions.get(session_id)

    async def run(
        self,
        workflow_name: str,
        description: str,
        project_name: str = "",
        mode: str = "auto",
        on_progress: Any = None,
    ) -> str:
        """
        执行指定的工作流。

        Args:
            workflow_name: 工作流名称。
            description: 任务描述。
            project_name: 项目名称。
            mode: "auto" (全自动) 或 "step" (只执行第一步后暂停)。
            on_progress: 进度回调。
        """
        workflow = WORKFLOWS.get(workflow_name)
        if not workflow:
            return f"错误: 未知工作流 '{workflow_name}'。可用: {', '.join(WORKFLOWS.keys())}"

        session_id = str(uuid.uuid4())[:8]
        session = WorkflowSession(
            session_id=session_id,
            workflow=workflow,
            description=description,
            project_name=project_name,
            started_at=time.time(),
        )
        self.sessions[session_id] = session

        if mode == "auto":
            return await self._run_all(session, on_progress)
        else:
            # 分步模式：执行第一步
            result = await self.next_step(session_id, on_progress=on_progress)
            return (
                f"🚀 **工作流会话已开启 (分步模式)**\nID: `{session_id}`\n\n"
                f"{session.status_summary()}\n\n"
                f"--- \n"
                f"### 步骤 1 产出:\n{result}\n\n"
                f"--- \n"
                f"💡 你可以使用 `workflow_control` 工具来控制后续步骤：继续、跳过、注入内容或结束。"
            )

    async def next_step(
        self,
        session_id: str,
        on_progress: Any = None,
    ) -> str:
        """执行会话的下一个步骤。"""
        session = self.get_session(session_id)
        if not session:
            return f"错误: 未找到会话 `{session_id}`"
        
        if session.is_complete:
            return "错误: 该工作流已完成"

        step_idx = session.current_step
        step = session.workflow.steps[step_idx]
        agent_def = self.agent_manager.get_agent(step.agent)
        
        if not agent_def:
            error = f"错误: Agent '{step.agent}' 不存在"
            session.step_outputs.append(error)
            session.step_statuses.append("error")
            session.current_step += 1
            return error

        # 通知进度
        if on_progress:
            await on_progress(step_idx + 1, session.total_steps, step.agent, step.label, "running")

        logger.info(f"会话 {session_id} 步骤 {step_idx + 1}/{session.total_steps}: "
                f"{agent_def.emoji} {agent_def.title} - {step.label}")

        # 计算项目目录
        project_dir = ""
        if session.project_name:
            project_dir = str(self.workspace / "projects" / session.project_name)
        else:
            project_dir = str(self.workspace)

        # 构建任务
        task = step.task_template.format(
            description=session.description,
            prev_output=session.prev_output,
            project_dir=project_dir,
        )

        try:
            result = await self.subagent_manager.run_with_agent(
                agent_def=agent_def,
                agent_manager=self.agent_manager,
                task=task,
                context=session.prev_output,
                project_dir=project_dir,
            )
            status = "success"
        except Exception as e:
            # 保留完整的异常信息（避免 str(e) 为空）
            err_desc = f"{type(e).__name__}: {e}" if str(e) else repr(e)
            result = f"执行失败: {err_desc}"
            status = "error"
            logger.error(f"步骤 {step_idx + 1} 失败: {err_desc}")

            # 检测是否有部分文件已写入（Developer 可能在崩溃前已创建了文件）
            if project_dir:
                import os
                try:
                    written_files = []
                    for root, dirs, files in os.walk(project_dir):
                        for f in files:
                            if not f.startswith('.') and f != 'workflow-report.md':
                                rel = os.path.relpath(os.path.join(root, f), project_dir)
                                written_files.append(rel)
                    if written_files:
                        result += f"\n\nℹ️ 部分文件已写入 ({len(written_files)} 个):\n"
                        result += "\n".join(f"  - {f}" for f in sorted(written_files)[:20])
                        logger.info(f"步骤 {step_idx + 1} 失败但已写入 {len(written_files)} 个文件")
                except Exception:
                    pass  # 不影响主流程

        # 保存产出物（最低质量门禁：内容超过 100 字符才保存）
        min_save_length = 100
        if step.save_as and session.project_name and status == "success" and len(result) >= min_save_length:
            project_dir = self.workspace / "projects" / session.project_name
            project_dir.mkdir(parents=True, exist_ok=True)
            output_path = project_dir / step.save_as
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result, encoding="utf-8")
        elif step.save_as and status == "success" and len(result) < min_save_length:
            logger.warning(
                f"步骤 {step_idx + 1} 产出内容过短 ({len(result)} 字符)，"
                f"跳过保存 {step.save_as}"
            )

        session.step_outputs.append(result)
        session.step_statuses.append(status)
        session.current_step += 1
        
        if session.is_complete:
            session.finished = True

        if on_progress:
            await on_progress(session.current_step, session.total_steps, step.agent, step.label, status)

        return result

    async def skip_step(self, session_id: str) -> str:
        """跳过当前步骤。"""
        session = self.get_session(session_id)
        if not session: return f"错误: 未找到会话 `{session_id}`"
        if session.is_complete: return "错误: 工作流已完成"

        step_idx = session.current_step
        step = session.workflow.steps[step_idx]
        session.step_outputs.append("")
        session.step_statuses.append("skipped")
        session.current_step += 1
        return f"已跳过步骤 {step_idx + 1}: {step.label} ({step.agent})"

    async def inject_step(self, session_id: str, content: str) -> str:
        """在当前步骤注入手动结果，并作为下一步的输入。"""
        session = self.get_session(session_id)
        if not session: return f"错误: 未找到会话 `{session_id}`"
        if session.is_complete: return "错误: 工作流已完成"

        step_idx = session.current_step
        step = session.workflow.steps[step_idx]
        
        # 如果该步骤需要保存文件，也保存注入的内容
        if step.save_as and session.project_name:
            project_dir = self.workspace / "projects" / session.project_name
            project_dir.mkdir(parents=True, exist_ok=True)
            output_path = project_dir / step.save_as
            output_path.write_text(content, encoding="utf-8")

        session.step_outputs.append(content)
        session.step_statuses.append("injected")
        session.current_step += 1
        return f"成功为步骤 {step_idx + 1}: {step.label} 注入手动成果内容。"

    async def _run_all(self, session: WorkflowSession, on_progress: Any = None) -> str:
        """内部全自动连跑。"""
        start_time = time.time()
        
        while not session.is_complete:
            await self.next_step(session.session_id, on_progress=on_progress)
        
        total_duration = time.time() - start_time
        success_count = sum(1 for s in session.step_statuses if s in ("success", "injected"))
        total_steps = session.total_steps

        # 构建报告
        workflow = session.workflow
        report_lines = [
            f"# 📦 工作流报告: {workflow.title} ({session.session_id})",
            f"\n**任务**: {session.description}",
            f"**状态**: 完成",
            f"**耗时**: {total_duration:.1f}s",
            f"**成功步骤**: {success_count}/{total_steps}\n",
            "---\n",
        ]

        for i, step in enumerate(workflow.steps):
            status = session.step_statuses[i] if i < len(session.step_statuses) else "pending"
            status_emoji = {"success": "✅", "error": "❌", "skipped": "⏭️", "injected": "📌"}.get(status, "⬜")
            report_lines.append(f"## {status_emoji} 步骤 {i + 1}: {step.label} ({step.agent})\n")
            if i < len(session.step_outputs):
                output = session.step_outputs[i]
                # 截断过长的步骤输出以控制报告总长度
                # 完整内容已通过 save_as 保存到文件
                if len(output) > 3000:
                    output = output[:3000] + "\n\n... [输出已截断，完整内容已保存到项目目录]"
                report_lines.append(output)
            report_lines.append("\n---\n")

        report = "\n".join(report_lines)

        # 保存报告
        if session.project_name:
            project_dir = self.workspace / "projects" / session.project_name
            project_dir.mkdir(parents=True, exist_ok=True)
            report_path = project_dir / "workflow-report.md"
            report_path.write_text(report, encoding="utf-8")

        return report


# ── 工作流工具 ────────────────────────────────────────────────────────


class RunWorkflowTool(Tool):
    """通过工具调用执行预定义的开发工作流。"""

    def __init__(self, engine: WorkflowEngine):
        self._engine = engine

    @property
    def name(self) -> str:
        return "run_workflow"

    @property
    def description(self) -> str:
        flows = ", ".join(
            f"{w.title}({w.name})" for w in WORKFLOWS.values()
        )
        return (
            f"启动预定义的开发流水线。支持全自动模式(auto)和分步交互模式(step)。\n"
            f"可用工作流: {flows}。\n"
            f"分步模式允许你在每步之后介入、修改产出或手动委派其他任务。"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow": {
                    "type": "string",
                    "description": "工作流名称",
                    "enum": list(WORKFLOWS.keys()),
                },
                "description": {
                    "type": "string",
                    "description": "任务描述，会传递给工作流中的每个Agent",
                },
                "project_name": {
                    "type": "string",
                    "description": "（可选）项目名称，用于保存产出物",
                },
                "mode": {
                    "type": "string",
                    "description": "执行模式：'auto' (连跑直到完成) 或 'step' (执行一步后暂停并等待指令)",
                    "enum": ["auto", "step"],
                    "default": "auto",
                },
            },
            "required": ["workflow", "description"],
        }

    async def execute(
        self,
        workflow: str,
        description: str,
        project_name: str = "",
        mode: str = "auto",
        **kwargs: Any,
    ) -> str:
        """执行工作流。"""
        return await self._engine.run(
            workflow_name=workflow,
            description=description,
            project_name=project_name,
            mode=mode,
        )


class WorkflowControlTool(Tool):
    """用于控制当前进行中的分步工作流会话。"""

    def __init__(self, engine: WorkflowEngine):
        self._engine = engine

    @property
    def name(self) -> str:
        return "workflow_control"

    @property
    def description(self) -> str:
        return (
            "控制分步执行的工作流会话。支持: \n"
            "- next: 执行下一个预定步骤\n"
            "- skip: 跳过当前预定步骤\n"
            "- inject: 注入手动提供的内容作为当前步骤的结果（将传给下一步）\n"
            "- status: 查看会话进度状态\n"
            "- abort: 强制结束会话"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "工作流会话 ID (从 run_workflow 输出中获得)",
                },
                "command": {
                    "type": "string",
                    "description": "控制指令",
                    "enum": ["next", "skip", "inject", "status", "abort"],
                },
                "content": {
                    "type": "string",
                    "description": "注入的内容（仅当 command='inject' 时需要）",
                },
            },
            "required": ["session_id", "command"],
        }

    async def execute(
        self,
        session_id: str,
        command: str,
        content: str = "",
        **kwargs: Any,
    ) -> str:
        """执行控制指令。"""
        session = self._engine.get_session(session_id)
        if not session:
            return f"错误: 未找到会话 `{session_id}`"

        if command == "status":
            return session.status_summary()

        if command == "abort":
            session.finished = True
            return f"❌ 会话 `{session_id}` 已强制终止。"

        if command == "next":
            result = await self._engine.next_step(session_id)
            if session.is_complete:
                return f"🏁 工作流步骤完成 (最后一步)。\n\n{result}"
            return (
                f"✅ 步骤 {session.current_step} 完成。\n\n"
                f"{session.status_summary()}\n\n"
                f"--- \n"
                f"### 步骤产出:\n{result}"
            )

        if command == "skip":
            msg = await self._engine.skip_step(session_id)
            if session.is_complete:
                return f"🏁 步骤已跳过。工作流完成。\n\n{msg}"
            return f"✅ {msg}\n\n{session.status_summary()}"

        if command == "inject":
            if not content:
                return "错误: 使用 'inject' 指令时必须提供 'content' 参数。"
            msg = await self._engine.inject_step(session_id, content)
            if session.is_complete:
                return f"🏁 内容已注入。工作流完成。\n\n{msg}"
            return f"✅ {msg}\n\n{session.status_summary()}"

        return f"未知指令: {command}"
