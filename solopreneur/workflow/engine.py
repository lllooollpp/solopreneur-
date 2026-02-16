"""���������� - ���Ŷ�AgentЭ���Ŀ�����ˮ�ߣ�֧���Զ�/�ֲ�/���ģʽ��"""

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
    from solopreneur.agent.core.subagent import SubagentManager
    from solopreneur.agent.definitions.manager import AgentManager

from solopreneur.agent.core.tools.base import Tool


@dataclass
class WorkflowStep:
    """��������һ�����衣"""

    agent: str  # ִ�иò���� Agent ���ƣ�ԭ role��
    
    # ���������ԣ�role ����ָ�� agent
    @property
    def role(self) -> str:
        return self.agent
    task_template: str  # ��������ģ�壬�ɰ��� {description} �� {prev_output} ռλ��
    label: str  # �����ǩ
    save_as: str = ""  # ���������ļ������������ĿĿ¼������ղ�����


@dataclass
class Workflow:
    """Ԥ����Ŀ�����������"""

    name: str  # ��������ʶ
    title: str  # ��ʾ����
    description: str  # ����������
    steps: list[WorkflowStep] = field(default_factory=list)


@dataclass
class WorkflowSession:
    """�ֲ��������Ự������ִ�н��ȡ�"""

    session_id: str
    workflow: Workflow
    description: str
    project_name: str
    project_dir: str = ""
    current_step: int = 0  # ��һ����ִ�еĲ������� (0-based)
    step_outputs: list[str] = field(default_factory=list)  # ÿ�������
    step_statuses: list[str] = field(default_factory=list)  # "success" | "error" | "skipped" | "injected"
    started_at: float = 0.0
    finished: bool = False

    def resolved_project_dir(self, workspace: Path) -> Path:
        """�������ι�����ʵ��ʹ�õ���ĿĿ¼��"""
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
        """���һ������Ч�����"""
        for output in reversed(self.step_outputs):
            if output:
                return output
        return ""

    @property
    def is_complete(self) -> bool:
        return self.current_step >= self.total_steps or self.finished

    def status_summary(self) -> str:
        """���ػỰ״̬ժҪ��"""
        lines = [
            f"?? **������**: {self.workflow.title} (`{self.workflow.name}`)",
            f"?? **�Ự**: `{self.session_id}`",
            f"?? **����**: {self.description}",
            f"?? **����**: {self.current_step}/{self.total_steps} ��",
        ]
        # ����ɲ���
        for i, step in enumerate(self.workflow.steps):
            if i < len(self.step_statuses):
                emoji = {"success": "?", "error": "?", "skipped": "??", "injected": "??"}.get(
                    self.step_statuses[i], "?"
                )
                lines.append(f"  {emoji} ���� {i + 1}: {step.label} ({step.agent})")
            elif i == self.current_step:
                lines.append(f"  ?? ���� {i + 1}: {step.label} ({step.agent}) �� **��ǰ����**")
            else:
                lines.append(f"  ? ���� {i + 1}: {step.label} ({step.agent})")
        
        if self.finished:
            lines.append("\n?? **״̬**: �����")
        else:
            next_step = self.workflow.steps[self.current_step]
            lines.append(f"\n?? **Tech Lead �������**:")
            lines.append(f"1. �������������")
            lines.append(f"2. ������⣬����ִ��: `workflow_control(session_id=\"{self.session_id}\", command=\"next\")`��")
            lines.append(f"3. �����Ҫ�޸ģ�����ʹ�� `delegate` ������ `workflow_control(..., command=\"inject\")` ע��������")
            
        return "\n".join(lines)


# ���� Ԥ���幤���� ������������������������������������������������������������������������������������������������������������

FEATURE_WORKFLOW = Workflow(
    name="feature",
    title="���ܿ���",
    description="�����Ĺ��ܿ������̣�������� �� �ܹ���� �� ����ʵ�� �� ������� �� ����",
    steps=[
        WorkflowStep(
            agent="product_manager",
            label="�������",
            task_template=(
                "�������¹������������Ʒ�����ĵ���PRD����\n"
                "��Ŀ����: ��Ŀ�����浽 `{project_dir}`\n\n{description}"
            ),
            save_as="docs/requirements.md",
        ),
        WorkflowStep(
            agent="architect",
            label="�ܹ����",
            task_template=(
                "�������������ĵ�����Ƽ���������\n"
                "��ĿĿ¼: `{project_dir}`\n\n"
                "# ԭʼ����\n{description}\n\n"
                "# ��Ʒ�����ĵ�\n{prev_output}"
            ),
            save_as="docs/architecture.md",
        ),
        WorkflowStep(
            agent="developer",
            label="����ʵ��",
            task_template=(
                "�������¼�����Ʒ������б���ʵ�֡�\n\n"
                "## ��Ҫ����ĿĿ¼\n"
                "���д����ļ����봴������ĿĿ¼�£�`{project_dir}`\n"
                "�����ʹ�� `write_file` �����ڸ�Ŀ¼�´���ʵ�ʵ�Դ�����ļ���.py, .js, .html, .css �ȣ���"
                "�����ǽ��������������ݡ�\n"
                "������ `list_dir` �鿴��ĿĿ¼�ṹ��Ȼ�󴴽���Ҫ���ļ���\n\n"
                "## ������ɵĲ���\n"
                "1. �� `{project_dir}` �´�����������Ŀ�ṹ��Ŀ¼���ļ���\n"
                "2. ʹ�� `write_file` д��ÿ��Դ�����ļ�����������\n"
                "3. ���谲װ������ʹ�� `exec` ����ִ�а�װ����\n"
                "4. �������������ļ��嵥\n\n"
                "# ԭʼ����\n{description}\n\n"
                "# �������\n{prev_output}"
            ),
        ),
        WorkflowStep(
            agent="code_reviewer",
            label="�������",
            task_template=(
                "��鱾�ι��ܿ����Ĵ�������\n"
                "��ĿĿ¼: `{project_dir}`\n"
                "��ʹ�� `list_dir` �� `read_file` �鿴��Ŀʵ�ʴ����ļ�������顣\n\n"
                "# ��������\n{description}\n\n"
                "# �����߱���\n{prev_output}"
            ),
            save_as="docs/review.md",
        ),
        WorkflowStep(
            agent="security_engineer",
            label="��ȫ���",
            task_template=(
                "���ڵ�ǰʵ�ֽ���Ӧ�ð�ȫ��鲢������ִ���޸����顣\n"
                "��ĿĿ¼: `{project_dir}`\n"
                "��ʹ�� `list_dir` / `read_file` ����֤�ݻ���顣\n\n"
                "# ��������\n{description}\n\n"
                "# ���������\n{prev_output}"
            ),
            save_as="docs/security-review.md",
        ),
        WorkflowStep(
            agent="tester",
            label="����",
            task_template=(
                "Ϊ���¹��ܱ�д��ִ�в��ԡ�\n"
                "��ĿĿ¼: `{project_dir}`\n\n"
                "## ?? ǿ��Ҫ��\n"
                "1. ʹ�� `list_dir` �鿴��ĿĿ¼���˽���Ŀ�ṹ�ͼ���ջ\n"
                "2. ʹ�� `read_file` �Ķ����д��룬���ʵ��ϸ��\n"
                "3. ʹ�� `write_file` ���������ļ�\n"
                "4. **����ʹ�� `exec` ����ʵ�����в���**������ֻ������������\n"
                "5. �������ʧ�ܣ��޸����Ⲣ��������\n"
                "6. �������ղ��Խ����ͨ��/ʧ��������\n\n"
                "## ��ֹ��Ϊ\n"
                "- ? ��Ҫֻ���'����ִ����������'\n"
                "- ? ��Ҫֻ����������в���\n"
                "- ? ����ʵ�ʵ��� exec �������в��鿴���\n\n"
                "## ?? E2E ���ԣ�ǰ��/Web ��Ŀ���룩\n"
                "�����Ŀ���� HTML/CSS/JS ��ǰ�˿�� (React/Vue/Svelte ��)��\n"
                "�����ʹ�� Playwright ��д������ E2E ���ԣ�\n"
                "```\n"
                "exec: npx playwright install --with-deps chromium\n"
                "write_file: e2e/basic.spec.ts  # �� e2e/test_basic.py\n"
                "exec: npx playwright test --reporter=list\n"
                "```\n"
                "�� Playwright ���û�һ����֤���ܣ���ҳ�桢���� UI���������\n\n"
                "## ?? Git �ύ\n"
                "������ɺ�ʹ�� `git` �����ύ�����ļ���\n"
                "```\n"
                "git: action=add, files=['.']\n"
                "git: action=commit, message='test: add tests for <feature>'\n"
                "```\n\n"
                "# ��������\n{description}\n\n"
                "# ��ȫ����������鷴��\n{prev_output}"
            ),
        ),
    ],
)

BUGFIX_WORKFLOW = Workflow(
    name="bugfix",
    title="Bug �޸�",
    description="Bug �޸����̣�������� �� �޸�ʵ�� �� ������� �� ������֤",
    steps=[
        WorkflowStep(
            agent="developer",
            label="����������޸�",
            task_template=(
                "�������޸����� Bug��\n"
                "��ĿĿ¼: `{project_dir}`\n"
                "��ʹ�� `list_dir` �� `read_file` �鿴���룬"
                "ʹ�� `write_file` �� `edit_file` �޸����⡣\n\n{description}"
            ),
        ),
        WorkflowStep(
            agent="code_reviewer",
            label="�޸����",
            task_template=(
                "������� Bug �޸��Ĵ�������\n"
                "��ĿĿ¼: `{project_dir}`\n\n"
                "# Bug ����\n{description}\n\n"
                "# �޸�����\n{prev_output}"
            ),
            save_as="docs/bugfix-review.md",
        ),
        WorkflowStep(
            agent="tester",
            label="�ع����",
            task_template=(
                "������� Bug �޸���д�ع���Բ�ִ�С�\n"
                "��ĿĿ¼: `{project_dir}`\n\n"
                "# Bug ����\n{description}\n\n"
                "# �޸������\n{prev_output}"
            ),
        ),
    ],
)

REVIEW_WORKFLOW = Workflow(
    name="review",
    title="�������",
    description="��������������̣������� �� ��ȫ��� �� ���Բ��佨��",
    steps=[
        WorkflowStep(
            agent="code_reviewer",
            label="�������",
            task_template=(
                "������´��������\n"
                "��ĿĿ¼: `{project_dir}`\n\n{description}"
            ),
            save_as="docs/review.md",
        ),
        WorkflowStep(
            agent="tester",
            label="���Խ���",
            task_template=(
                "���ݴ��������������Ҫ����Ĳ��ԡ�\n"
                "��ĿĿ¼: `{project_dir}`\n\n"
                "# �������\n{description}\n\n"
                "# �����\n{prev_output}"
            ),
        ),
    ],
)

DEPLOY_WORKFLOW = Workflow(
    name="deploy",
    title="��������",
    description="�������̣�������֤ �� �������� �� ����",
    steps=[
        WorkflowStep(
            agent="tester",
            label="����ǰ����",
            task_template=(
                "ִ�в���ǰ������������֤��\n"
                "��ĿĿ¼: `{project_dir}`\n\n{description}"
            ),
        ),
        WorkflowStep(
            agent="release_manager",
            label="����׼��",
            task_template=(
                "׼�������嵥�����߻ع�������\n"
                "��ĿĿ¼: `{project_dir}`\n\n"
                "# ����Ŀ��\n{description}\n\n"
                "# ���Խ��\n{prev_output}"
            ),
            save_as="docs/release-plan.md",
        ),
        WorkflowStep(
            agent="devops",
            label="����������ִ��",
            task_template=(
                "���ò�ִ�в���\n"
                "��ĿĿ¼: `{project_dir}`\n\n"
                "# ��������\n{description}\n\n"
                "# ����׼��\n{prev_output}"
            ),
            save_as="docs/deployment.md",
        ),
        WorkflowStep(
            agent="sre_engineer",
            label="��������֤",
            task_template=(
                "ִ�з������ȶ�����֤��ɹ۲��Լ�顣\n"
                "��ĿĿ¼: `{project_dir}`\n"
                "������澯��SLO ��ع���ս��ۡ�\n\n"
                "# ������Ϣ\n{description}\n\n"
                "# ������\n{prev_output}"
            ),
            save_as="docs/post-deploy-validation.md",
        ),
    ],
)

# ������ע���
WORKFLOWS: dict[str, Workflow] = {
    w.name: w
    for w in (FEATURE_WORKFLOW, BUGFIX_WORKFLOW, REVIEW_WORKFLOW, DEPLOY_WORKFLOW)
}


# ���� ����ֽ���ʾ�ʣ�effc.md Initializer Agent������������������������������������������

_DECOMPOSE_PROMPT = """����һ������ֽ�ר�ҡ��뽫������Ŀ����ֽ�Ϊ�����ġ������������Ĺ��ܵ�(Feature)��

## ��������
{description}

## ���Ҫ��
����� JSON ���飬ÿ�����ܰ��������ֶΣ�
- id: Ψһ��ʶ����ʽ FEAT-001, FEAT-002, ...
- category: ���� (core / ui / api / infra / test)
- priority: ���ȼ� (P0=���ı��� / P1=��Ҫ / P2=ê�����)
- description: ����������һ�仰��������ȷ��
- steps: ʵ�ֲ��裨�ַ������飬3-5 ����
- test_criteria: ���ձ�׼��һ�仰��

## �ֽ�ԭ��
1. ÿ�� Feature Ӧ�ÿ�����һ�� workflow ѭ������ɣ�Լ 15-30 ���ӣ�
2. P0 �������ȣ�ȷ�����Ĺ�����ʵ��
3. ����֮�������ͨ�����ȼ�������P0 ������P1 ������
4. ÿ�� Feature ����������ȷ�����ձ�׼
5. �е���Ŀͨ�� 8-20 �� Feature��������Ŀ 20-50 ��
6. ��Ҫ��©������ʩ Feature����Ŀ��ʼ����������װ�����õȣ�

����� JSON ���飬��Ҫ���� markdown �����������ı���
"""


# ���� ���������� ��������������������������������������������������������������������������������������������������������������


class WorkflowEngine:
    """
    ִ��Ԥ����Ŀ�����������

    �𲽵��ò�ͬAgent���� Agent����ÿ���������ݸ���һ����
    �������м���ﵽ��ĿĿ¼��
    ֧���Զ���ˮ��ģʽ�ͷֲ�����ģʽ��

    ���� LongRunningHarness��effc.md ģʽ����
    - ÿ����ɺ��Զ���¼���ȵ� progress.md
    - ���ղ����������Ž�
    - ֧�ֿ�Ự��������
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
        self._harness = None  # LongRunningHarness�����ⲿ����

    def set_harness(self, harness) -> None:
        """ע�� LongRunningHarness ������ effc.md ����ģʽ��"""
        self._harness = harness

    # ���� Git �뻷������ ����������������������������������������������������������������������������������������

    def _ensure_git_repo(self, project_dir: Path) -> None:
        """ȷ����ĿĿ¼��һ�� Git �ֿ⣨effc.md: ��ʼ git �ύ����"""
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
            # ����Ĭ���û��������״� commit �����
            subprocess.run(
                ["git", "config", "user.email", "solopreneur@local"],
                cwd=str(project_dir),
                capture_output=True, timeout=5,
            )
            subprocess.run(
                ["git", "config", "user.name", "solopreneur"],
                cwd=str(project_dir),
                capture_output=True, timeout=5,
            )
            logger.info(f"Git �ֿ��ѳ�ʼ��: {project_dir}")
        except Exception as e:
            logger.warning(f"Git init ʧ�ܣ���������������: {e}")

    def _git_commit(self, project_dir: Path, message: str) -> bool:
        """����ĿĿ¼ִ�� git add + commit��effc.md: ÿ�� feature �ύ����"""
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
            logger.warning(f"Git commit ʧ�ܣ���������: {e}")
            return False

    def _generate_init_sh(self, project_dir: Path) -> None:
        """ΪĿ����Ŀ���� init.sh ����ű���effc.md: Initializer Agent ���ܣ���"""
        init_sh = project_dir / "init.sh"
        if init_sh.exists():
            return
        content = """#!/bin/bash
# Auto-generated by solopreneur workflow engine (effc.md pattern)
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
            logger.warning(f"���� init.sh ʧ��: {e}")

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
        ִ��ָ���Ĺ�������

        Args:
            workflow_name: ���������ơ�
            description: ����������
            project_name: ��Ŀ���ơ�
            mode: "auto" (ȫ�Զ�) �� "step" (ִֻ�е�һ������ͣ)��
            on_progress: ���Ȼص���
        """
        workflow = WORKFLOWS.get(workflow_name)
        if not workflow:
            return f"����: δ֪������ '{workflow_name}'������: {', '.join(WORKFLOWS.keys())}"

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
            # �ֲ�ģʽ��ִ�е�һ��
            result = await self.next_step(session_id, on_progress=on_progress)
            return (
                f"?? **�������Ự�ѿ��� (�ֲ�ģʽ)**\nID: `{session_id}`\n\n"
                f"{session.status_summary()}\n\n"
                f"--- \n"
                f"### ���� 1 ����:\n{result}\n\n"
                f"--- \n"
                f"?? �����ʹ�� `workflow_control` ���������ƺ������裺������������ע�����ݻ������"
            )

    async def next_step(
        self,
        session_id: str,
        on_progress: Any = None,
    ) -> str:
        """ִ�лỰ����һ�����衣"""
        session = self.get_session(session_id)
        if not session:
            return f"����: δ�ҵ��Ự `{session_id}`"
        
        if session.is_complete:
            return "����: �ù����������"

        step_idx = session.current_step
        step = session.workflow.steps[step_idx]
        agent_def = self.agent_manager.get_agent(step.agent)
        
        if not agent_def:
            error = f"����: Agent '{step.agent}' ������"
            session.step_outputs.append(error)
            session.step_statuses.append("error")
            session.current_step += 1
            return error

        # ֪ͨ����
        if on_progress:
            await on_progress(step_idx + 1, session.total_steps, step.agent, step.label, "running")

        logger.info(f"�Ự {session_id} ���� {step_idx + 1}/{session.total_steps}: "
                f"{agent_def.emoji} {agent_def.title} - {step.label}")

        # ������ĿĿ¼
        project_dir = str(session.resolved_project_dir(self.workspace))

        # ��������
        task = step.task_template.format(
            description=session.description,
            prev_output=session.prev_output,
            project_dir=project_dir,
        )

        # Harness ������ע�룺�� Subagent �˽���Ŀ�������
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

            # ���� Harness ���ȼ�¼��effc.md ģʽ������
            if self._harness:
                try:
                    self._harness.record_progress(
                        f"?? ���������� {step_idx + 1}/{session.total_steps} "
                        f"[{step.label}] ({step.agent}) ���"
                    )
                except Exception as he:
                    logger.warning(f"Harness ��¼����ʧ��: {he}")

        except Exception as e:
            # �����������쳣��Ϣ������ str(e) Ϊ�գ�
            err_desc = f"{type(e).__name__}: {e}" if str(e) else repr(e)
            result = f"ִ��ʧ��: {err_desc}"
            status = "error"
            logger.error(f"���� {step_idx + 1} ʧ��: {err_desc}")

            # Harness ��¼ʧ�ܲ���
            if self._harness:
                try:
                    self._harness.record_progress(
                        f"? ���������� {step_idx + 1}/{session.total_steps} "
                        f"[{step.label}] ({step.agent}) ʧ��: {err_desc[:200]}"
                    )
                except Exception:
                    pass

            # ����Ƿ��в����ļ���д�루Developer �����ڱ���ǰ�Ѵ������ļ���
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
                        result += f"\n\n?? �����ļ���д�� ({len(written_files)} ��):\n"
                        result += "\n".join(f"  - {f}" for f in sorted(written_files)[:20])
                        logger.info(f"���� {step_idx + 1} ʧ�ܵ���д�� {len(written_files)} ���ļ�")
                except Exception:
                    pass  # ��Ӱ��������

        # ����������������Ž������ݳ��� 100 �ַ��ű��棩
        min_save_length = 100
        if step.save_as and status == "success" and len(result) >= min_save_length:
            project_dir_path = session.resolved_project_dir(self.workspace)
            project_dir_path.mkdir(parents=True, exist_ok=True)
            output_path = project_dir_path / step.save_as
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result, encoding="utf-8")
        elif step.save_as and status == "success" and len(result) < min_save_length:
            logger.warning(
                f"���� {step_idx + 1} �������ݹ��� ({len(result)} �ַ�)��"
                f"�������� {step.save_as}"
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
        """������ǰ���衣"""
        session = self.get_session(session_id)
        if not session: return f"����: δ�ҵ��Ự `{session_id}`"
        if session.is_complete: return "����: �����������"

        step_idx = session.current_step
        step = session.workflow.steps[step_idx]
        session.step_outputs.append("")
        session.step_statuses.append("skipped")
        session.current_step += 1
        return f"���������� {step_idx + 1}: {step.label} ({step.agent})"

    async def inject_step(self, session_id: str, content: str) -> str:
        """�ڵ�ǰ����ע���ֶ����������Ϊ��һ�������롣"""
        session = self.get_session(session_id)
        if not session: return f"����: δ�ҵ��Ự `{session_id}`"
        if session.is_complete: return "����: �����������"

        step_idx = session.current_step
        step = session.workflow.steps[step_idx]
        
        # ����ò�����Ҫ�����ļ���Ҳ����ע�������
        if step.save_as:
            project_dir = session.resolved_project_dir(self.workspace)
            project_dir.mkdir(parents=True, exist_ok=True)
            output_path = project_dir / step.save_as
            output_path.write_text(content, encoding="utf-8")

        session.step_outputs.append(content)
        session.step_statuses.append("injected")
        session.current_step += 1
        return f"�ɹ�Ϊ���� {step_idx + 1}: {step.label} ע���ֶ��ɹ����ݡ�"

    async def _post_workflow_validation(self, session: WorkflowSession) -> None:
        """
        ��������ɺ��������֤��effc.md ����ģʽ����

        ��飺
        1. ���һ����tester��������Ƿ����ʵ�ʲ���ִ��
        2. �Ƿ����в��趼�ɹ�
        3. ��¼���״̬�� Harness
        """
        if not self._harness:
            return

        try:
            success_count = sum(1 for s in session.step_statuses if s in ("success", "injected"))
            total_steps = session.total_steps
            all_success = success_count == total_steps

            # ������һ����ͨ���� tester���Ƿ�ֻ����˽����û��ʵ��ִ��
            last_output = session.step_outputs[-1] if session.step_outputs else ""
            tester_warning = ""
            if session.workflow.steps and session.workflow.steps[-1].agent == "tester":
                no_exec_indicators = [
                    "�������ڱ���ִ��",
                    "���ֶ�����",
                    "����ִ����������",
                    "recommend running",
                    "please run",
                ]
                if any(ind in last_output for ind in no_exec_indicators):
                    tester_warning = " ?? Tester δʵ��ִ�в��ԣ�������˽���"

            self._harness.record_progress(
                f"?? ������ [{session.workflow.title}] ��� "
                f"({success_count}/{total_steps} �ɹ�)"
                f"{tester_warning}"
            )

            if not all_success:
                failed_steps = [
                    f"{i+1}:{session.workflow.steps[i].label}"
                    for i, s in enumerate(session.step_statuses)
                    if s == "error"
                ]
                self._harness.record_progress(
                    f"?? ʧ�ܲ���: {', '.join(failed_steps)} �� ��Ҫ�޸�������"
                )
        except Exception as e:
            logger.warning(f"����������֤ʧ��: {e}")

    def _get_next_feature_directive(self, session: WorkflowSession) -> str:
        """
        ��������ѭ��ָ�
        
        ��� Harness �л���δ��ɵ� feature������һ����ȷ��ָ��
        �������� Agent �������� run_workflow ����������һ�� feature��
        
        ���� effc.md ����ģʽ�ĺ��ģ�һ�� feature ��ɺ��Զ��ν���һ����
        """
        if not self._harness:
            return ""

        try:
            pending = self._harness.list_features(status="pending")
            in_progress = self._harness.list_features(status="in_progress")

            remaining = pending + in_progress
            if not remaining:
                return (
                    "\n## ?? ���� Feature �����\n\n"
                    "Harness ��û�и��������� Feature����Ŀ������ɡ�\n"
                )

            next_feat = remaining[0]
            feat_id = next_feat.get("id", "?")
            feat_desc = next_feat.get("description", "")
            feat_priority = next_feat.get("priority", "P1")

            completed = self._harness.list_features(status="completed")
            total = len(completed) + len(remaining)

            return (
                f"\n## ? �������� - ��һ�� Feature\n\n"
                f"**����**: {len(completed)}/{total} ����ɣ�"
                f"ʣ�� {len(remaining)} ��\n\n"
                f"**��һ�� Feature**:\n"
                f"- ID: `{feat_id}`\n"
                f"- ���ȼ�: {feat_priority}\n"
                f"- ����: {feat_desc}\n\n"
                f"**?? ���������ж�**: ���������� `run_workflow` ���ߣ�"
                f"�� `{feat_desc}` ��Ϊ description ����������\n"
                f"��Ҫͣ�����ܽ�����'��һ���ƻ�'��ֱ�ӵ��ù��߼�����\n"
            )
        except Exception as e:
            logger.warning(f"��ȡ��һ�� Feature ָ��ʧ��: {e}")
            return ""

    async def _run_all(self, session: WorkflowSession, on_progress: Any = None) -> str:
        """�ڲ�ȫ�Զ����ܣ����� effc.md ������֤����"""
        start_time = time.time()

        # ���� effc.md ����׼�� ����
        project_dir = session.resolved_project_dir(self.workspace)
        self._ensure_git_repo(project_dir)
        self._generate_init_sh(project_dir)

        # ���� effc.md ����ѭ�����Զ��ֽ������� Feature ���� ����
        if self._harness:
            try:
                incremental = await self._try_incremental(
                    session, on_progress, start_time
                )
                if incremental is not None:
                    return incremental
            except Exception as e:
                logger.warning(
                    f"����ģʽ�쳣�����˵���ͨģʽ: {e}", exc_info=True
                )

        # ���� ����Ϊ��ͨ���ι�����ģʽ������·��������
        # Harness����¼��������ʼ
        if self._harness:
            try:
                self._harness.record_progress(
                    f"?? ������ [{session.workflow.title}] ��ʼִ�� "
                    f"({session.total_steps} ����)"
                )
            except Exception as he:
                logger.warning(f"Harness ��¼��ʼʧ��: {he}")

        while not session.is_complete:
            await self.next_step(session.session_id, on_progress=on_progress)

        # ���� ��������ɺ��������֤��effc.md ����ģʽ������
        await self._post_workflow_validation(session)

        total_duration = time.time() - start_time
        success_count = sum(1 for s in session.step_statuses if s in ("success", "injected"))
        total_steps = session.total_steps

        # ��������
        workflow = session.workflow
        report_lines = [
            f"# ?? ����������: {workflow.title} ({session.session_id})",
            f"\n**����**: {session.description}",
            f"**״̬**: ���",
            f"**��ʱ**: {total_duration:.1f}s",
            f"**�ɹ�����**: {success_count}/{total_steps}\n",
            "---\n",
        ]

        for i, step in enumerate(workflow.steps):
            status = session.step_statuses[i] if i < len(session.step_statuses) else "pending"
            status_emoji = {"success": "?", "error": "?", "skipped": "??", "injected": "??"}.get(status, "?")
            report_lines.append(f"## {status_emoji} ���� {i + 1}: {step.label} ({step.agent})\n")
            if i < len(session.step_outputs):
                output = session.step_outputs[i]
                # �ضϹ����Ĳ�������Կ��Ʊ����ܳ���
                # ����������ͨ�� save_as ���浽�ļ�
                if len(output) > 3000:
                    output = output[:3000] + "\n\n... [����ѽضϣ����������ѱ��浽��ĿĿ¼]"
                report_lines.append(output)
            report_lines.append("\n---\n")

        # ���� ����ѭ��ָ�effc.md ģʽ������
        # ��� Harness �л���δ��ɵ� feature����ȷ���� Agent ����
        next_feature_directive = self._get_next_feature_directive(session)
        if next_feature_directive:
            report_lines.append(next_feature_directive)

        report = "\n".join(report_lines)

        # ���汨��
        if session.project_name or session.project_dir:
            project_dir = session.resolved_project_dir(self.workspace)
            project_dir.mkdir(parents=True, exist_ok=True)
            report_path = project_dir / "workflow-report.md"
            report_path.write_text(report, encoding="utf-8")

        return report

    # ���� effc.md ����ѭ������ ����������������������������������������������������������������������������������

    async def _try_incremental(
        self,
        session: WorkflowSession,
        on_progress: Any,
        start_time: float,
    ) -> str | None:
        """
        ���� effc.md ����ģʽִ�С�

        1. ��� Harness û�� feature_list����ͨ�� LLM �ֽ�����
        2. ��� Feature ִ�й����� pipeline
        3. ÿ�� Feature ��ɺ�ͨ�� Harness �Ž�

        Returns:
            ���������ַ������������������ģʽ�򷵻� None�����˵���ͨģʽ����
        """
        if not self._harness:
            return None

        # ȷ�� harness �ѳ�ʼ����������ֽ⣩
        if not self._harness.is_initialized():
            try:
                await self._decompose_requirements(session)
            except Exception as e:
                logger.warning(f"����ֽ�ʧ�ܣ�������ͨģʽ: {e}")
                return None

        # ����Ƿ��д������ Feature
        pending = self._harness.list_features(status="pending")
        in_progress = self._harness.list_features(status="in_progress")
        remaining = in_progress + pending

        if not remaining:
            completed = self._harness.list_features(status="completed")
            if completed:
                return (
                    "# ?? ���� Feature �����\n\n"
                    f"�� {len(completed)} �� Feature ȫ����ɡ���Ŀ������ϡ�"
                )
            return None  # û�� Feature ���ݣ����˵���ͨģʽ

        # ���� �Ự������ԣ�effc.md: getting up to speed�� ����
        try:
            startup_result = self._harness.run_session_startup_tests()
            if startup_result and not startup_result.get("all_passed", True):
                failed = startup_result.get("failed", [])
                self._harness.record_progress(
                    f"?? �Ự�������ʧ�� ({len(failed)} ��)��"
                    f"�����޸���������"
                )
                logger.warning(
                    f"Session startup tests failed: {failed}"
                )
        except Exception as e:
            logger.debug(f"Session startup tests skipped: {e}")

        # ���� ����ѭ������ ����
        MAX_FEATURES_PER_RUN = 10
        MAX_TIME_PER_RUN = 3600  # 1 Сʱ��ȫ����
        all_reports: list[str] = []
        features_attempted = 0

        self._harness.record_progress(
            f"?? ����ѭ����ʼ (������: {len(remaining)} �� Feature)"
        )

        for _ in range(MAX_FEATURES_PER_RUN):
            if time.time() - start_time > MAX_TIME_PER_RUN:
                self._harness.record_progress("? ����ѭ��ʱ�����Ƶ���")
                break

            current = self._harness.get_enforced_current_feature()
            if not current or current.get("status") == "completed":
                break

            feat_id = current.get("id", f"FEAT-{features_attempted + 1:03d}")
            feat_desc = current.get("description", session.description)
            logger.info(f"�T�T�T ����ѭ��: Feature {feat_id} - {feat_desc} �T�T�T")

            # ��ʼ Feature��Harness �Ž���ڣ�
            if current.get("status") == "pending":
                self._harness.start_feature(feat_id)

            # ִ������������ pipeline
            report = await self._run_single_feature(
                session, feat_id, feat_desc, on_progress
            )
            all_reports.append(report)
            features_attempted += 1

            # �Ž����ڣ�������� Feature
            try:
                result = self._harness.complete_feature(
                    feat_id,
                    notes="Workflow completed",
                    verify_clean=False,
                    run_tests=False,
                )
                if result.get("success"):
                    self._harness.record_progress(
                        f"? Feature {feat_id} ���"
                    )
                else:
                    self._harness.record_progress(
                        f"?? Feature {feat_id} �Ž�δͨ��: "
                        f"{result.get('message', '')[:200]}"
                    )
            except Exception as e:
                logger.warning(f"Feature {feat_id} ��ɴ����쳣: {e}")
                try:
                    self._harness.transition_feature_status(
                        feat_id, "completed",
                        reason=f"��������ִ�У��Ž��쳣: {e}",
                    )
                except Exception:
                    pass

        # ���� ���ܱ��� ����
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
            "# ?? ������������",
            f"\n**����**: {session.description}",
            f"**ģʽ**: effc.md ����ѭ��",
            f"**����**: {completed_total}/{len(all_features)} Feature �����",
            f"**����**: {features_attempted} �� Feature",
            f"**ʣ��**: {remaining_count} ��",
            f"**��ʱ**: {total_duration:.1f}s\n",
            "---\n",
        ]

        for i, fr in enumerate(all_reports):
            report_lines.append(f"## Feature {i + 1}\n")
            if len(fr) > 2000:
                fr = fr[:2000] + "\n... [�ѽض�]"
            report_lines.append(fr)
            report_lines.append("\n---\n")

        if remaining_count > 0:
            report_lines.append(
                f"\n## ?? ʣ�� {remaining_count} �� Feature\n\n"
                "�ٴε��� `run_workflow` �����Զ�������\n"
            )

        report = "\n".join(report_lines)

        # ���汨��
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
        """Ϊ���� Feature ���������Ĺ����� pipeline��"""
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
                f"?? Feature [{feat_id}] ��������ʼ: {feat_desc}"
            )

        while not feature_session.is_complete:
            await self.next_step(session_id, on_progress=on_progress)

        await self._post_workflow_validation(feature_session)

        # effc.md: ÿ�� Feature ��ɺ��Զ� git commit
        project_dir = feature_session.resolved_project_dir(self.workspace)
        self._git_commit(
            project_dir,
            f"feat({feat_id}): {feat_desc[:60]}"
        )

        # ���� Feature ����
        success_count = sum(
            1 for s in feature_session.step_statuses
            if s in ("success", "injected")
        )
        lines = [
            f"**Feature**: {feat_id} - {feat_desc}",
            f"**���**: {success_count}/{feature_session.total_steps} ����ɹ�",
        ]
        for i, step in enumerate(feature_session.workflow.steps):
            if i < len(feature_session.step_statuses):
                emoji = {
                    "success": "?", "error": "?",
                    "skipped": "??", "injected": "??",
                }.get(feature_session.step_statuses[i], "?")
                lines.append(f"  {emoji} {step.label} ({step.agent})")

        if feature_session.step_outputs:
            last = feature_session.step_outputs[-1]
            if len(last) > 500:
                last = last[:500] + "..."
            lines.append(f"\n**��������ժҪ**:\n{last}")

        return "\n".join(lines)

    async def _decompose_requirements(
        self, session: WorkflowSession
    ) -> None:
        """
        ʹ�� LLM ������ֽ�Ϊ Feature �б��д�� Harness��

        ��Ӧ effc.md �е� Initializer Agent���ڵ�һ�� session
        ���߲������ɿ����������� Feature �嵥��
        """
        logger.info(f"��ʼ�ֽ�����: {session.description[:100]}")

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
                "����ֽ�δ���� Feature��ʹ��ԭʼ������Ϊ��һ Feature"
            )
            features = [
                {
                    "id": "FEAT-001",
                    "category": "core",
                    "priority": "P0",
                    "description": session.description,
                    "steps": ["ʵ����������"],
                    "test_criteria": "���ܿ���������",
                    "status": "pending",
                }
            ]

        project_name = session.project_name or "project"
        self._harness.initialize(project_name, features)

        # effc.md: ��ʼ git �ύ������ feature_list.json �� init.sh��
        project_dir = session.resolved_project_dir(self.workspace)
        self._ensure_git_repo(project_dir)
        self._generate_init_sh(project_dir)
        self._git_commit(
            project_dir,
            f"chore: initialize project with {len(features)} features"
        )

        logger.info(f"�����ѷֽ�Ϊ {len(features)} �� Feature")
        self._harness.record_progress(
            f"?? ����ֽ����: {len(features)} �� Feature"
        )

    def _parse_feature_json(self, content: str) -> list[dict]:
        """�� LLM ��Ӧ�н��� Feature JSON��"""
        # ֱ�ӽ���
        try:
            data = json.loads(content.strip())
            if isinstance(data, list):
                return self._normalize_features(data)
            if isinstance(data, dict) and "features" in data:
                return self._normalize_features(data["features"])
        except json.JSONDecodeError:
            pass

        # ��ȡ JSON �����
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

        # ����ԣ���ȡ����� [...]
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    return self._normalize_features(data)
            except json.JSONDecodeError:
                pass

        logger.warning(f"�޷����� Feature JSON: {content[:200]}")
        return []

    def _normalize_features(self, features: list[dict]) -> list[dict]:
        """��׼�� Feature ���ݣ�ȷ����Ҫ�ֶδ��ڡ�"""
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
        Ϊ Subagent ���� Harness ������ժҪ��

        ��ÿ�� Subagent �˽���Ŀ������Ⱥ͵�ǰ Feature ״̬��
        �����ظ�ʵ������ɵĹ��ܡ�
        """
        if not self._harness or not self._harness.is_initialized():
            return ""

        try:
            ctx = self._harness.get_session_context()
            stats = ctx.get("statistics", {})
            current = ctx.get("current_feature")

            lines = [
                "# ��Ŀ����������",
                f"- �ܽ���: {stats.get('completed', 0)}/{stats.get('total', 0)} Feature �����",
                f"- ������: {stats.get('in_progress', 0)}",
                f"- ������: {stats.get('pending', 0)}",
            ]

            if current:
                lines.extend([
                    "\n## ��ǰ Feature",
                    f"- ID: {current.get('id', '?')}",
                    f"- ����: {current.get('description', '')}",
                    f"- ���ձ�׼: {current.get('test_criteria', 'δ����')}",
                ])

            return "\n".join(lines)
        except Exception as e:
            logger.debug(f"��ȡ Harness ������ʧ��: {e}")
            return ""


# ���� ���������� ����������������������������������������������������������������������������������������������������������������


class RunWorkflowTool(Tool):
    """ͨ�����ߵ���ִ��Ԥ����Ŀ�����������"""

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
            f"���Ԥ����Ŀ�����ˮ�ߡ�֧��ȫ�Զ�ģʽ(auto)�ͷֲ�����ģʽ(step)��\n"
            f"���ù�����: {flows}��\n"
            f"�ֲ�ģʽ��������ÿ��֮����롢�޸Ĳ������ֶ�ί����������"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "workflow": {
                    "type": "string",
                    "description": "����������",
                    "enum": list(WORKFLOWS.keys()),
                },
                "description": {
                    "type": "string",
                    "description": "�����������ᴫ�ݸ��������е�ÿ��Agent",
                },
                "project_name": {
                    "type": "string",
                    "description": "����ѡ����Ŀ���ƣ����ڱ��������",
                },
                "project_dir": {
                    "type": "string",
                    "description": "����ѡ����Ŀ����·�����ṩ������ʹ�ø�·�������������ļ���",
                },
                "mode": {
                    "type": "string",
                    "description": "ִ��ģʽ��'auto' (����ֱ�����) �� 'step' (ִ��һ������ͣ���ȴ�ָ��)",
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
        """ִ�й�������"""
        return await self._engine.run(
            workflow_name=workflow,
            description=description,
            project_name=project_name,
            project_dir=project_dir,
            mode=mode,
        )


class WorkflowControlTool(Tool):
    """���ڿ��Ƶ�ǰ�����еķֲ��������Ự��"""

    def __init__(self, engine: WorkflowEngine):
        self._engine = engine

    @property
    def name(self) -> str:
        return "workflow_control"

    @property
    def description(self) -> str:
        return (
            "���Ʒֲ�ִ�еĹ������Ự��֧��: \n"
            "- next: ִ����һ��Ԥ������\n"
            "- skip: ������ǰԤ������\n"
            "- inject: ע���ֶ��ṩ��������Ϊ��ǰ����Ľ������������һ����\n"
            "- status: �鿴�Ự����״̬\n"
            "- abort: ǿ�ƽ����Ự"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "�������Ự ID (�� run_workflow ����л��)",
                },
                "command": {
                    "type": "string",
                    "description": "����ָ��",
                    "enum": ["next", "skip", "inject", "status", "abort"],
                },
                "content": {
                    "type": "string",
                    "description": "ע������ݣ����� command='inject' ʱ��Ҫ��",
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
        """ִ�п���ָ�"""
        session = self._engine.get_session(session_id)
        if not session:
            return f"����: δ�ҵ��Ự `{session_id}`"

        if command == "status":
            return session.status_summary()

        if command == "abort":
            session.finished = True
            return f"? �Ự `{session_id}` ��ǿ����ֹ��"

        if command == "next":
            result = await self._engine.next_step(session_id)
            if session.is_complete:
                return f"?? ������������� (���һ��)��\n\n{result}"
            return (
                f"? ���� {session.current_step} ��ɡ�\n\n"
                f"{session.status_summary()}\n\n"
                f"--- \n"
                f"### �������:\n{result}"
            )

        if command == "skip":
            msg = await self._engine.skip_step(session_id)
            if session.is_complete:
                return f"?? ��������������������ɡ�\n\n{msg}"
            return f"? {msg}\n\n{session.status_summary()}"

        if command == "inject":
            if not content:
                return "����: ʹ�� 'inject' ָ��ʱ�����ṩ 'content' ������"
            msg = await self._engine.inject_step(session_id, content)
            if session.is_complete:
                return f"?? ������ע�롣��������ɡ�\n\n{msg}"
            return f"? {msg}\n\n{session.status_summary()}"

        return f"δָ֪��: {command}"
