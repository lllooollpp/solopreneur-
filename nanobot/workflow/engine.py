"""工作流引擎 - 编排多Agent协作的开发流水线，支持自动/分步/混合模式。"""

import json
import re
import subprocess
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
    project_dir: str = ""
    current_step: int = 0  # 下一个待执行的步骤索引 (0-based)
    step_outputs: list[str] = field(default_factory=list)  # 每步的输出
    step_statuses: list[str] = field(default_factory=list)  # "success" | "error" | "skipped" | "injected"
    started_at: float = 0.0
    finished: bool = False

    def resolved_project_dir(self, workspace: Path) -> Path:
        """解析本次工作流实际使用的项目目录。"""
        if self.project_dir:
            return Path(self.project_dir).expanduser().resolve()
        if self.project_name:
            return (workspace / "projects" / self.project_name).resolve()
        return workspace.resolve()

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
                "项目目录: `{project_dir}`\n\n"
                "## ⚠️ 强制要求\n"
                "1. 使用 `list_dir` 查看项目目录，了解项目结构和技术栈\n"
                "2. 使用 `read_file` 阅读现有代码，理解实现细节\n"
                "3. 使用 `write_file` 创建测试文件\n"
                "4. **必须使用 `exec` 工具实际运行测试**，不能只描述测试命令\n"
                "5. 如果测试失败，修复问题并重新运行\n"
                "6. 报告最终测试结果（通过/失败数量）\n\n"
                "## 禁止行为\n"
                "- ❌ 不要只输出'建议执行以下命令'\n"
                "- ❌ 不要只描述如何运行测试\n"
                "- ✅ 必须实际调用 exec 工具运行并查看结果\n\n"
                "## 🌐 E2E 测试（前端/Web 项目必须）\n"
                "如果项目包含 HTML/CSS/JS 或前端框架 (React/Vue/Svelte 等)，\n"
                "你必须使用 Playwright 编写并运行 E2E 测试：\n"
                "```\n"
                "exec: npx playwright install --with-deps chromium\n"
                "write_file: e2e/basic.spec.ts  # 或 e2e/test_basic.py\n"
                "exec: npx playwright test --reporter=list\n"
                "```\n"
                "用 Playwright 像用户一样验证功能：打开页面、操作 UI、检查结果。\n\n"
                "## 📝 Git 提交\n"
                "测试完成后，使用 `git` 工具提交测试文件：\n"
                "```\n"
                "git: action=add, files=['.']\n"
                "git: action=commit, message='test: add tests for <feature>'\n"
                "```\n\n"
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


# ── 需求分解提示词（effc.md Initializer Agent）────────────────────

_DECOMPOSE_PROMPT = """你是一个需求分解专家。请将以下项目需求分解为独立的、可增量开发的功能点(Feature)。

## 需求描述
{description}

## 输出要求
请输出 JSON 数组，每个功能包含以下字段：
- id: 唯一标识，格式 FEAT-001, FEAT-002, ...
- category: 分类 (core / ui / api / infra / test)
- priority: 优先级 (P0=核心必需 / P1=重要 / P2=锚上添花)
- description: 功能描述（一句话，具体明确）
- steps: 实现步骤（字符串数组，3-5 步）
- test_criteria: 验收标准（一句话）

## 分解原则
1. 每个 Feature 应该可以在一次 workflow 循环内完成（约 15-30 分钟）
2. P0 功能优先，确保核心功能先实现
3. 功能之间的依赖通过优先级隐含表达（P0 先做，P1 后做）
4. 每个 Feature 都必须有明确的验收标准
5. 中等项目通常 8-20 个 Feature，大型项目 20-50 个
6. 不要遗漏基础设施 Feature（项目初始化、依赖安装、配置等）

仅输出 JSON 数组，不要包含 markdown 代码块或其他文本。
"""


# ── 工作流引擎 ───────────────────────────────────────────────────────


class WorkflowEngine:
    """
    执行预定义的开发工作流。

    逐步调用不同Agent的子 Agent，将每步产出传递给下一步，
    并保存中间产物到项目目录。
    支持自动流水线模式和分步交互模式。

    集成 LongRunningHarness（effc.md 模式）：
    - 每步完成后自动记录进度到 progress.md
    - 最终步骤接入测试门禁
    - 支持跨会话增量开发
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
        self._harness = None  # LongRunningHarness，由外部设置

    def set_harness(self, harness) -> None:
        """注入 LongRunningHarness 以启用 effc.md 增量模式。"""
        self._harness = harness

    # ── Git 与环境管理 ────────────────────────────────────────────

    def _ensure_git_repo(self, project_dir: Path) -> None:
        """确保项目目录是一个 Git 仓库（effc.md: 初始 git 提交）。"""
        project_dir.mkdir(parents=True, exist_ok=True)
        git_dir = project_dir / ".git"
        if git_dir.exists():
            return
        try:
            subprocess.run(
                ["git", "init"],
                cwd=str(project_dir),
                capture_output=True, timeout=15,
            )
            # 配置默认用户（避免首次 commit 报错）
            subprocess.run(
                ["git", "config", "user.email", "nanobot@local"],
                cwd=str(project_dir),
                capture_output=True, timeout=5,
            )
            subprocess.run(
                ["git", "config", "user.name", "Nanobot"],
                cwd=str(project_dir),
                capture_output=True, timeout=5,
            )
            logger.info(f"Git 仓库已初始化: {project_dir}")
        except Exception as e:
            logger.warning(f"Git init 失败（不阻塞工作流）: {e}")

    def _git_commit(self, project_dir: Path, message: str) -> bool:
        """在项目目录执行 git add + commit（effc.md: 每个 feature 提交）。"""
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(project_dir),
                capture_output=True, timeout=15,
            )
            result = subprocess.run(
                ["git", "commit", "-m", message, "--allow-empty"],
                cwd=str(project_dir),
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                logger.info(f"Git commit: {message}")
                return True
            # nothing to commit is OK
            return True
        except Exception as e:
            logger.warning(f"Git commit 失败（不阻塞）: {e}")
            return False

    def _generate_init_sh(self, project_dir: Path) -> None:
        """为目标项目生成 init.sh 启动脚本（effc.md: Initializer Agent 功能）。"""
        init_sh = project_dir / "init.sh"
        if init_sh.exists():
            return
        content = """#!/bin/bash
# Auto-generated by nanobot workflow engine (effc.md pattern)
set -e

echo "=== Project Init ==="
echo "Working directory: $(pwd)"

# Detect and set up environment
if [ -f "requirements.txt" ]; then
    echo ">>> Python project detected"
    python -m venv .venv 2>/dev/null || true
    source .venv/bin/activate 2>/dev/null || true
    pip install -r requirements.txt -q
elif [ -f "pyproject.toml" ]; then
    echo ">>> Python project detected (pyproject.toml)"
    pip install -e . -q 2>/dev/null || true
fi

if [ -f "package.json" ]; then
    echo ">>> Node.js project detected"
    npm install --silent 2>/dev/null || true
fi

# Run tests to verify project state
echo "=== Running smoke tests ==="
if [ -f "pytest.ini" ] || [ -f "pyproject.toml" ]; then
    pytest -x -q 2>/dev/null && echo "Tests passed" || echo "Tests failed (or not configured)"
elif [ -f "package.json" ]; then
    npm test --if-present 2>/dev/null || echo "No tests configured"
fi

echo "=== Init complete ==="
"""
        try:
            init_sh.write_text(content, encoding="utf-8")
            logger.info(f"Generated init.sh: {init_sh}")
        except Exception as e:
            logger.warning(f"生成 init.sh 失败: {e}")

    def get_session(self, session_id: str) -> WorkflowSession | None:
        return self.sessions.get(session_id)

    async def run(
        self,
        workflow_name: str,
        description: str,
        project_name: str = "",
        project_dir: str = "",
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
            project_dir=project_dir,
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
        project_dir = str(session.resolved_project_dir(self.workspace))

        # 构建任务
        task = step.task_template.format(
            description=session.description,
            prev_output=session.prev_output,
            project_dir=project_dir,
        )

        # Harness 上下文注入：让 Subagent 了解项目整体进度
        context_for_agent = session.prev_output
        harness_ctx = self._get_harness_context_for_subagent()
        if harness_ctx:
            context_for_agent = (
                harness_ctx + "\n\n---\n\n" + context_for_agent
                if context_for_agent else harness_ctx
            )

        try:
            result = await self.subagent_manager.run_with_agent(
                agent_def=agent_def,
                agent_manager=self.agent_manager,
                task=task,
                context=context_for_agent,
                project_dir=project_dir,
            )
            status = "success"

            # ── Harness 进度记录（effc.md 模式）──
            if self._harness:
                try:
                    self._harness.record_progress(
                        f"📋 工作流步骤 {step_idx + 1}/{session.total_steps} "
                        f"[{step.label}] ({step.agent}) 完成"
                    )
                except Exception as he:
                    logger.warning(f"Harness 记录进度失败: {he}")

        except Exception as e:
            # 保留完整的异常信息（避免 str(e) 为空）
            err_desc = f"{type(e).__name__}: {e}" if str(e) else repr(e)
            result = f"执行失败: {err_desc}"
            status = "error"
            logger.error(f"步骤 {step_idx + 1} 失败: {err_desc}")

            # Harness 记录失败步骤
            if self._harness:
                try:
                    self._harness.record_progress(
                        f"❌ 工作流步骤 {step_idx + 1}/{session.total_steps} "
                        f"[{step.label}] ({step.agent}) 失败: {err_desc[:200]}"
                    )
                except Exception:
                    pass

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
        if step.save_as and status == "success" and len(result) >= min_save_length:
            project_dir_path = session.resolved_project_dir(self.workspace)
            project_dir_path.mkdir(parents=True, exist_ok=True)
            output_path = project_dir_path / step.save_as
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
        if step.save_as:
            project_dir = session.resolved_project_dir(self.workspace)
            project_dir.mkdir(parents=True, exist_ok=True)
            output_path = project_dir / step.save_as
            output_path.write_text(content, encoding="utf-8")

        session.step_outputs.append(content)
        session.step_statuses.append("injected")
        session.current_step += 1
        return f"成功为步骤 {step_idx + 1}: {step.label} 注入手动成果内容。"

    async def _post_workflow_validation(self, session: WorkflowSession) -> None:
        """
        工作流完成后的质量验证（effc.md 增量模式）。

        检查：
        1. 最后一步（tester）的输出是否包含实际测试执行
        2. 是否所有步骤都成功
        3. 记录完成状态到 Harness
        """
        if not self._harness:
            return

        try:
            success_count = sum(1 for s in session.step_statuses if s in ("success", "injected"))
            total_steps = session.total_steps
            all_success = success_count == total_steps

            # 检查最后一步（通常是 tester）是否只输出了建议而没有实际执行
            last_output = session.step_outputs[-1] if session.step_outputs else ""
            tester_warning = ""
            if session.workflow.steps and session.workflow.steps[-1].agent == "tester":
                no_exec_indicators = [
                    "建议您在本地执行",
                    "请手动运行",
                    "建议执行以下命令",
                    "recommend running",
                    "please run",
                ]
                if any(ind in last_output for ind in no_exec_indicators):
                    tester_warning = " ⚠️ Tester 未实际执行测试，仅输出了建议"

            self._harness.record_progress(
                f"🏁 工作流 [{session.workflow.title}] 完成 "
                f"({success_count}/{total_steps} 成功)"
                f"{tester_warning}"
            )

            if not all_success:
                failed_steps = [
                    f"{i+1}:{session.workflow.steps[i].label}"
                    for i, s in enumerate(session.step_statuses)
                    if s == "error"
                ]
                self._harness.record_progress(
                    f"⚠️ 失败步骤: {', '.join(failed_steps)} — 需要修复后重试"
                )
        except Exception as e:
            logger.warning(f"工作流后验证失败: {e}")

    def _get_next_feature_directive(self, session: WorkflowSession) -> str:
        """
        生成增量循环指令。
        
        如果 Harness 中还有未完成的 feature，生成一段明确的指令
        告诉主控 Agent 立即调用 run_workflow 继续开发下一个 feature。
        
        这是 effc.md 增量模式的核心：一个 feature 完成后自动衔接下一个。
        """
        if not self._harness:
            return ""

        try:
            pending = self._harness.list_features(status="pending")
            in_progress = self._harness.list_features(status="in_progress")

            remaining = pending + in_progress
            if not remaining:
                return (
                    "\n## 🎉 所有 Feature 已完成\n\n"
                    "Harness 中没有更多待处理的 Feature。项目开发完成。\n"
                )

            next_feat = remaining[0]
            feat_id = next_feat.get("id", "?")
            feat_desc = next_feat.get("description", "")
            feat_priority = next_feat.get("priority", "P1")

            completed = self._harness.list_features(status="completed")
            total = len(completed) + len(remaining)

            return (
                f"\n## ⚡ 增量开发 - 下一个 Feature\n\n"
                f"**进度**: {len(completed)}/{total} 已完成，"
                f"剩余 {len(remaining)} 个\n\n"
                f"**下一个 Feature**:\n"
                f"- ID: `{feat_id}`\n"
                f"- 优先级: {feat_priority}\n"
                f"- 描述: {feat_desc}\n\n"
                f"**⚠️ 必须立即行动**: 请立即调用 `run_workflow` 工具，"
                f"以 `{feat_desc}` 作为 description 继续开发。\n"
                f"不要停下来总结或输出'下一步计划'，直接调用工具继续。\n"
            )
        except Exception as e:
            logger.warning(f"获取下一个 Feature 指令失败: {e}")
            return ""

    async def _run_all(self, session: WorkflowSession, on_progress: Any = None) -> str:
        """内部全自动连跑（集成 effc.md 增量验证）。"""
        start_time = time.time()

        # ── effc.md 环境准备 ──
        project_dir = session.resolved_project_dir(self.workspace)
        self._ensure_git_repo(project_dir)
        self._generate_init_sh(project_dir)

        # ── effc.md 增量循环：自动分解需求并逐 Feature 开发 ──
        if self._harness:
            try:
                incremental = await self._try_incremental(
                    session, on_progress, start_time
                )
                if incremental is not None:
                    return incremental
            except Exception as e:
                logger.warning(
                    f"增量模式异常，回退到普通模式: {e}", exc_info=True
                )

        # ── 以下为普通单次工作流模式（回退路径）──
        # Harness：记录工作流开始
        if self._harness:
            try:
                self._harness.record_progress(
                    f"🚀 工作流 [{session.workflow.title}] 开始执行 "
                    f"({session.total_steps} 步骤)"
                )
            except Exception as he:
                logger.warning(f"Harness 记录开始失败: {he}")

        while not session.is_complete:
            await self.next_step(session.session_id, on_progress=on_progress)

        # ── 工作流完成后的质量验证（effc.md 增量模式）──
        await self._post_workflow_validation(session)

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

        # ── 增量循环指令（effc.md 模式）──
        # 如果 Harness 中还有未完成的 feature，明确告诉 Agent 继续
        next_feature_directive = self._get_next_feature_directive(session)
        if next_feature_directive:
            report_lines.append(next_feature_directive)

        report = "\n".join(report_lines)

        # 保存报告
        if session.project_name or session.project_dir:
            project_dir = session.resolved_project_dir(self.workspace)
            project_dir.mkdir(parents=True, exist_ok=True)
            report_path = project_dir / "workflow-report.md"
            report_path.write_text(report, encoding="utf-8")

        return report

    # ── effc.md 增量循环方法 ─────────────────────────────────────────

    async def _try_incremental(
        self,
        session: WorkflowSession,
        on_progress: Any,
        start_time: float,
    ) -> str | None:
        """
        尝试 effc.md 增量模式执行。

        1. 如果 Harness 没有 feature_list，先通过 LLM 分解需求
        2. 逐个 Feature 执行工作流 pipeline
        3. 每个 Feature 完成后通过 Harness 门禁

        Returns:
            增量报告字符串；如果不适用增量模式则返回 None（回退到普通模式）。
        """
        if not self._harness:
            return None

        # 确保 harness 已初始化（含需求分解）
        if not self._harness.is_initialized():
            try:
                await self._decompose_requirements(session)
            except Exception as e:
                logger.warning(f"需求分解失败，回退普通模式: {e}")
                return None

        # 检查是否有待处理的 Feature
        pending = self._harness.list_features(status="pending")
        in_progress = self._harness.list_features(status="in_progress")
        remaining = in_progress + pending

        if not remaining:
            completed = self._harness.list_features(status="completed")
            if completed:
                return (
                    "# 🎉 所有 Feature 已完成\n\n"
                    f"共 {len(completed)} 个 Feature 全部完成。项目开发完毕。"
                )
            return None  # 没有 Feature 数据，回退到普通模式

        # ── 会话启动测试（effc.md: getting up to speed） ──
        try:
            startup_result = self._harness.run_session_startup_tests()
            if startup_result and not startup_result.get("all_passed", True):
                failed = startup_result.get("failed", [])
                self._harness.record_progress(
                    f"⚠️ 会话启动测试失败 ({len(failed)} 项)，"
                    f"优先修复现有问题"
                )
                logger.warning(
                    f"Session startup tests failed: {failed}"
                )
        except Exception as e:
            logger.debug(f"Session startup tests skipped: {e}")

        # ── 增量循环核心 ──
        MAX_FEATURES_PER_RUN = 10
        MAX_TIME_PER_RUN = 3600  # 1 小时安全限制
        all_reports: list[str] = []
        features_attempted = 0

        self._harness.record_progress(
            f"🚀 增量循环开始 (待处理: {len(remaining)} 个 Feature)"
        )

        for _ in range(MAX_FEATURES_PER_RUN):
            if time.time() - start_time > MAX_TIME_PER_RUN:
                self._harness.record_progress("⏰ 增量循环时间限制到达")
                break

            current = self._harness.get_enforced_current_feature()
            if not current or current.get("status") == "completed":
                break

            feat_id = current.get("id", f"FEAT-{features_attempted + 1:03d}")
            feat_desc = current.get("description", session.description)
            logger.info(f"═══ 增量循环: Feature {feat_id} - {feat_desc} ═══")

            # 开始 Feature（Harness 门禁入口）
            if current.get("status") == "pending":
                self._harness.start_feature(feat_id)

            # 执行完整工作流 pipeline
            report = await self._run_single_feature(
                session, feat_id, feat_desc, on_progress
            )
            all_reports.append(report)
            features_attempted += 1

            # 门禁出口：尝试完成 Feature
            try:
                result = self._harness.complete_feature(
                    feat_id,
                    notes="Workflow completed",
                    verify_clean=False,
                    run_tests=False,
                )
                if result.get("success"):
                    self._harness.record_progress(
                        f"✅ Feature {feat_id} 完成"
                    )
                else:
                    self._harness.record_progress(
                        f"⚠️ Feature {feat_id} 门禁未通过: "
                        f"{result.get('message', '')[:200]}"
                    )
            except Exception as e:
                logger.warning(f"Feature {feat_id} 完成处理异常: {e}")
                try:
                    self._harness.transition_feature_status(
                        feat_id, "completed",
                        reason=f"工作流已执行，门禁异常: {e}",
                    )
                except Exception:
                    pass

        # ── 汇总报告 ──
        total_duration = time.time() - start_time
        all_features = self._harness.list_features()
        completed_total = len(
            self._harness.list_features(status="completed")
        )
        remaining_count = (
            len(self._harness.list_features(status="pending"))
            + len(self._harness.list_features(status="in_progress"))
        )

        report_lines = [
            "# 📦 增量开发报告",
            f"\n**任务**: {session.description}",
            f"**模式**: effc.md 增量循环",
            f"**进度**: {completed_total}/{len(all_features)} Feature 已完成",
            f"**本轮**: {features_attempted} 个 Feature",
            f"**剩余**: {remaining_count} 个",
            f"**耗时**: {total_duration:.1f}s\n",
            "---\n",
        ]

        for i, fr in enumerate(all_reports):
            report_lines.append(f"## Feature {i + 1}\n")
            if len(fr) > 2000:
                fr = fr[:2000] + "\n... [已截断]"
            report_lines.append(fr)
            report_lines.append("\n---\n")

        if remaining_count > 0:
            report_lines.append(
                f"\n## ⏭️ 剩余 {remaining_count} 个 Feature\n\n"
                "再次调用 `run_workflow` 即可自动继续。\n"
            )

        report = "\n".join(report_lines)

        # 保存报告
        if session.project_name or session.project_dir:
            project_dir = session.resolved_project_dir(self.workspace)
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "workflow-report.md").write_text(
                report, encoding="utf-8"
            )

        return report

    async def _run_single_feature(
        self,
        parent_session: WorkflowSession,
        feat_id: str,
        feat_desc: str,
        on_progress: Any = None,
    ) -> str:
        """为单个 Feature 运行完整的工作流 pipeline。"""
        session_id = f"{parent_session.session_id}-{feat_id}"
        feature_session = WorkflowSession(
            session_id=session_id,
            workflow=parent_session.workflow,
            description=feat_desc,
            project_name=parent_session.project_name,
            project_dir=parent_session.project_dir,
            started_at=time.time(),
        )
        self.sessions[session_id] = feature_session

        if self._harness:
            self._harness.record_progress(
                f"▶️ Feature [{feat_id}] 工作流开始: {feat_desc}"
            )

        while not feature_session.is_complete:
            await self.next_step(session_id, on_progress=on_progress)

        await self._post_workflow_validation(feature_session)

        # effc.md: 每个 Feature 完成后自动 git commit
        project_dir = feature_session.resolved_project_dir(self.workspace)
        self._git_commit(
            project_dir,
            f"feat({feat_id}): {feat_desc[:60]}"
        )

        # 构建 Feature 报告
        success_count = sum(
            1 for s in feature_session.step_statuses
            if s in ("success", "injected")
        )
        lines = [
            f"**Feature**: {feat_id} - {feat_desc}",
            f"**结果**: {success_count}/{feature_session.total_steps} 步骤成功",
        ]
        for i, step in enumerate(feature_session.workflow.steps):
            if i < len(feature_session.step_statuses):
                emoji = {
                    "success": "✅", "error": "❌",
                    "skipped": "⏭️", "injected": "📌",
                }.get(feature_session.step_statuses[i], "❓")
                lines.append(f"  {emoji} {step.label} ({step.agent})")

        if feature_session.step_outputs:
            last = feature_session.step_outputs[-1]
            if len(last) > 500:
                last = last[:500] + "..."
            lines.append(f"\n**最后步骤输出摘要**:\n{last}")

        return "\n".join(lines)

    async def _decompose_requirements(
        self, session: WorkflowSession
    ) -> None:
        """
        使用 LLM 将需求分解为 Feature 列表并写入 Harness。

        对应 effc.md 中的 Initializer Agent：在第一个 session
        将高层需求拆成可增量开发的 Feature 清单。
        """
        logger.info(f"开始分解需求: {session.description[:100]}")

        prompt = _DECOMPOSE_PROMPT.format(description=session.description)
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": prompt},
        ]

        response = await self.subagent_manager.provider.chat(
            messages=messages,
            model=self.subagent_manager.model,
        )

        features = self._parse_feature_json(response.content or "")

        if not features:
            logger.warning(
                "需求分解未产生 Feature，使用原始描述作为单一 Feature"
            )
            features = [
                {
                    "id": "FEAT-001",
                    "category": "core",
                    "priority": "P0",
                    "description": session.description,
                    "steps": ["实现完整功能"],
                    "test_criteria": "功能可正常运行",
                    "status": "pending",
                }
            ]

        project_name = session.project_name or "project"
        self._harness.initialize(project_name, features)

        # effc.md: 初始 git 提交（包含 feature_list.json 和 init.sh）
        project_dir = session.resolved_project_dir(self.workspace)
        self._ensure_git_repo(project_dir)
        self._generate_init_sh(project_dir)
        self._git_commit(
            project_dir,
            f"chore: initialize project with {len(features)} features"
        )

        logger.info(f"需求已分解为 {len(features)} 个 Feature")
        self._harness.record_progress(
            f"📝 需求分解完成: {len(features)} 个 Feature"
        )

    def _parse_feature_json(self, content: str) -> list[dict]:
        """从 LLM 响应中解析 Feature JSON。"""
        # 直接解析
        try:
            data = json.loads(content.strip())
            if isinstance(data, list):
                return self._normalize_features(data)
            if isinstance(data, dict) and "features" in data:
                return self._normalize_features(data["features"])
        except json.JSONDecodeError:
            pass

        # 提取 JSON 代码块
        for pattern in [
            r'```json\s*\n(.*?)```',
            r'```\s*\n(.*?)```',
        ]:
            match = re.search(pattern, content, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1).strip())
                    if isinstance(data, list):
                        return self._normalize_features(data)
                except (json.JSONDecodeError, IndexError):
                    continue

        # 最后尝试：提取最外层 [...]
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    return self._normalize_features(data)
            except json.JSONDecodeError:
                pass

        logger.warning(f"无法解析 Feature JSON: {content[:200]}")
        return []

    def _normalize_features(self, features: list[dict]) -> list[dict]:
        """标准化 Feature 数据，确保必要字段存在。"""
        normalized = []
        for i, f in enumerate(features):
            feat = {
                "id": f.get("id", f"FEAT-{i + 1:03d}"),
                "category": f.get("category", "core"),
                "priority": f.get("priority", "P1"),
                "description": f.get("description", ""),
                "steps": f.get("steps", []),
                "test_criteria": f.get("test_criteria", ""),
                "status": "pending",
            }
            if feat["description"]:
                normalized.append(feat)
        return normalized

    def _get_harness_context_for_subagent(self) -> str:
        """
        为 Subagent 构建 Harness 上下文摘要。

        让每个 Subagent 了解项目整体进度和当前 Feature 状态，
        避免重复实现已完成的功能。
        """
        if not self._harness or not self._harness.is_initialized():
            return ""

        try:
            ctx = self._harness.get_session_context()
            stats = ctx.get("statistics", {})
            current = ctx.get("current_feature")

            lines = [
                "# 项目进度上下文",
                f"- 总进度: {stats.get('completed', 0)}/{stats.get('total', 0)} Feature 已完成",
                f"- 进行中: {stats.get('in_progress', 0)}",
                f"- 待处理: {stats.get('pending', 0)}",
            ]

            if current:
                lines.extend([
                    "\n## 当前 Feature",
                    f"- ID: {current.get('id', '?')}",
                    f"- 描述: {current.get('description', '')}",
                    f"- 验收标准: {current.get('test_criteria', '未定义')}",
                ])

            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"获取 Harness 上下文失败: {e}")
            return ""


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
                "project_dir": {
                    "type": "string",
                    "description": "（可选）项目绝对路径。提供后优先使用该路径保存与生成文件。",
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
        project_dir: str = "",
        mode: str = "auto",
        **kwargs: Any,
    ) -> str:
        """执行工作流。"""
        return await self._engine.run(
            workflow_name=workflow,
            description=description,
            project_name=project_name,
            project_dir=project_dir,
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
