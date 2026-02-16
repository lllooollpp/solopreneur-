"""Context builder for assembling agent prompts."""

import base64
import mimetypes
from pathlib import Path
from typing import Any

from solopreneur.agent.core.memory import MemoryStore
from solopreneur.agent.core.skills import SkillsLoader


class ContextBuilder:
    """
    Builds the context (system prompt + messages) for the agent.
    
    Assembles bootstrap files, memory, skills, roles, and conversation history
    into a coherent prompt for the LLM.
    """
    
    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)
    
    def build_system_prompt(self, skill_names: list[str] | None = None, project_info: dict | None = None) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.
        
        Args:
            skill_names: Optional list of skills to include.
            project_info: Optional project information (id, name, path, etc.)
        
        Returns:
            Complete system prompt.
        """
        parts = []
        
        # Core identity
        parts.append(self._get_identity())
        
        # Current project context (if available)
        if project_info:
            project_context = self._build_project_context(project_info)
            if project_context:
                parts.append(project_context)
        
        # Bootstrap files
        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)
        
        # Memory context
        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")
        
        # Skills - progressive loading
        # 1. Always-loaded skills: include full content
        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")
        
        # 2. Available skills: only show summary (agent uses read_file to load)
        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")
        
        # 3. Agent 团队系统 - 让主 Agent 知道可以委派任务
        try:
            from solopreneur.agent.definitions.manager import AgentManager
            agent_mgr = AgentManager(self.workspace, self.skills)
            agents_summary = agent_mgr.build_agent_summary()
            if agents_summary:
                parts.append(agents_summary)
        except Exception:
            pass  # Agent 系统加载失败时静默跳�?
        
        return "\n\n---\n\n".join(parts)
    
    def _get_identity(self) -> str:
        """Get the core identity section."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())
        review_mode = self._get_review_mode()
        approval_policy = self._get_approval_policy_text(review_mode)
        
        return f"""# solopreneur 🐈

    You are solopreneur, a **Tech Lead (技术负责人)** who autonomously leads a software engineering team. You make decisions and execute efficiently under the configured approval mode.

### ⚠️ 最高优先级规则 (CRITICAL RULES)
1. **你是动态编排�?*。分析任务后，自主决定需要哪�?Agent、什么顺序、是否需要迭代。使�?`delegate` 工具逐步委派任务�?
2. **默认直接执行，不先停下来问确�?*。但遇到“人工审核模式”时，按审批策略执行确认流程�?
3. **绝不要问技术细�?*（如"�?MySQL 还是 PostgreSQL�?），自己选择合理默认值并在结果中声明假设�?
4. **仅在真正阻塞时才提问**（例如项目目录不存在、无权限、关键凭证缺失）�?

### 工作流程

#### 阶段 1: 快速建模（不阻塞）
当用户提出开发需求时，立即提取关键信息并形成执行假设�?

1. 提取项目路径（优先使用当前选中项目路径�?
2. 提取技术栈、核心功能边�?
3. 缺失项使用默认值，不等待用户确�?

#### 阶段 2: 持续执行（long-running�?
按增量方式持续推进，使用 `delegate_auto` / `delegate` / `run_workflow(mode="auto")`�?

1. **分析任务复杂�?*，制定编排计划：
    - 简单任务（�?写一�?hello world"）→ 只需 developer
    - 中等任务（如"审查代码"）→ code_reviewer / tester
    - 复杂任务（如"开�?RBAC 系统"）→ �?Agent 增量迭代

2. **每轮只推进一小步并留下工�?*�?
    - 维护进度文件（如 `.agent/progress.md`�?
    - 维护功能清单（如 `.agent/feature_list.json`�?
    - 产出代码后进行测试与校验，再进入下一�?

3. **编排原则**�?
   - 不是每个任务都需要所有角色参与，按需调度
   - 如果某个 Agent 的产出不达标，可以重新委派或委派给其�?Agent 修正
    - 你是决策者，根据实际情况灵活调整计划并持续推进，直到阶段目标完成

> **注意**: 对于“新项目/大功能”优先使�?`run_workflow(mode="auto")` �?`delegate_auto`，不要只发一条澄清消息就结束�?

### 审批策略（可配置�?
{approval_policy}

### 行为模式
- 用户�?实现 X 功能" �?**直接执行 + 动态编�?*
- 用户�?修复 X Bug" �?**直接执行 + delegate �?developer（必要时�?reviewer/tester�?*
- 用户�?审查代码" �?**直接 delegate �?code_reviewer**
- 用户�?按完整流程开�? �?使用 `run_workflow(mode=\"auto\")`
- 用户问简单问�?�?直接回答，不需要委�?

## Current Time
{now}

## Workspace
Your workspace is at: {workspace_path}
- Memory files: {workspace_path}/memory/MEMORY.md
- Daily notes: {workspace_path}/memory/YYYY-MM-DD.md
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md
- Project artifacts: {workspace_path}/projects/{{project-name}}/

## 执行原则

- 收到开发任�?�?**立即执行并持续推�?*，使�?delegate/delegate_auto/run_workflow 动态编�?
- 收到简单问�?�?直接回答，不需要委�?
- 收到模糊需�?�?**自己做合理假�?*后执行，并在产出中记录假�?
- 每次 delegate 返回�?�?评估结果，决定下一步行�?

IMPORTANT: When responding to direct questions or conversations, reply directly with your text response.
Only use the 'message' tool when you need to send a message to a specific chat channel (like WhatsApp),
or when current approval mode is manual and you are issuing an approval request.
For normal conversation (non-approval), respond with text.

Always be helpful, accurate, and concise. When using tools, explain what you're doing.
When remembering something, write to {workspace_path}/memory/MEMORY.md"""

    def _get_review_mode(self) -> str:
        """Read review mode from config with safe fallback."""
        try:
            from solopreneur.config.loader import load_config
            config = load_config()
            mode = getattr(config.agents.defaults, "review_mode", "auto")
            return mode if mode in ("auto", "manual") else "auto"
        except Exception:
            return "auto"

    def _get_approval_policy_text(self, review_mode: str) -> str:
        """Build approval policy text injected into system prompt."""
        if review_mode == "manual":
            return """- 当前模式: **manual（人工审核）**
- 当你准备执行“下一阶段/关键变更（如批量改文件、执行破坏性操作、跨模块重构）”时�?*优先使用 `message` 工具通知用户确认**，内容包含：
  1) 已完成内�?
  2) 下一步计�?
  3) 风险与影�?
- 然后**暂停推进**并等待用户明确确认（如“确�?继续/approve”）�?
- 收到确认后立即继续执行，不要重复提问�?""
        return """- 当前模式: **auto（自动审核）**
- 你可以在完成阶段性检查后自我审批并继续推进，不需要等待用户确认�?
- 仅在真正阻塞（缺权限/路径无效/关键凭证缺失）时才请求用户介入�?""
    
    def _load_bootstrap_files(self) -> str:
        """Load all bootstrap files from workspace."""
        parts = []
        encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin1"]
        
        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = None
                for enc in encodings:
                    try:
                        content = file_path.read_text(encoding=enc)
                        break
                    except UnicodeDecodeError:
                        continue
                if content is None:
                    continue
                parts.append(f"## {filename}\n\n{content}")
        
        return "\n\n".join(parts) if parts else ""
    
    def _build_project_context(self, project_info: dict) -> str:
        """Build project context section for system prompt."""
        if not project_info:
            return ""
        
        project_id = project_info.get("id", "unknown")
        project_name = project_info.get("name", "未命名项�?)
        project_path = project_info.get("path", "")
        project_desc = project_info.get("description", "")
        project_source = project_info.get("source", "local")
        env_vars = project_info.get("env_vars") or []
        
        context_parts = ["# 当前项目上下�?(Current Project Context)\n"]
        context_parts.append(f"**项目名称**: {project_name}")
        context_parts.append(f"**项目ID**: {project_id}")
        if project_desc:
            context_parts.append(f"**项目描述**: {project_desc}")
        context_parts.append(f"**项目路径**: {project_path}")
        context_parts.append(f"**项目来源**: {project_source}")
        
        # 添加重要提示
        context_parts.append("\n### ⚠️ 项目路径使用规则")
        context_parts.append(f"1. **当前工作目录**: {project_path}")
        context_parts.append("2. **所有文件操�?*都必须在此目录下进行")
        context_parts.append("3. **生成的代�?文档**必须保存到该目录")
        context_parts.append("4. 使用 `write_file` 工具时，路径以该目录为基�?)
        
        if project_source != "local" and project_info.get("git_info"):
            git_info = project_info["git_info"]
            context_parts.append(f"\n**Git 分支**: {git_info.get('branch', 'main')}")
            if git_info.get("last_sync"):
                context_parts.append(f"**最后同�?*: {git_info['last_sync']}")

        # 项目环境变量
        if env_vars:
            context_parts.append("\n## 📋 项目环境配置")
            context_parts.append("以下是本项目的环境信息，在生成配置文件、部署脚本、代码时请直接使用：")

            category_titles = {
                "database": "数据�?,
                "registry": "私服/镜像�?,
                "server": "服务地址",
                "middleware": "中间�?,
                "credential": "凭证",
                "general": "通用",
            }

            grouped: dict[str, list[dict]] = {}
            for item in env_vars:
                if not isinstance(item, dict):
                    continue
                cat = str(item.get("category") or "general")
                grouped.setdefault(cat, []).append(item)

            for cat in ["database", "registry", "server", "middleware", "credential", "general"]:
                items = grouped.get(cat, [])
                if not items:
                    continue
                title = category_titles.get(cat, cat)
                context_parts.append(f"\n### {title} ({cat})")
                context_parts.append("| 变量 | �?| 说明 |")
                context_parts.append("|------|----|------|")
                for item in items:
                    key = str(item.get("key") or "")
                    value = str(item.get("value") or "")
                    desc = str(item.get("description") or "")
                    sensitive = bool(item.get("sensitive"))
                    display_value = "******" if sensitive else value
                    if sensitive and desc:
                        desc = f"{desc} (sensitive)"
                    elif sensitive:
                        desc = "sensitive"
                    context_parts.append(f"| {key} | {display_value} | {desc} |")

            context_parts.append("\n⚠️ 以上信息为本项目的实际环境配置，请在生成代码、配置文件时直接引用，不要使用占位符�?)
        
        return "\n".join(context_parts)
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        project_info: dict | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            media: Optional list of local file paths for images/media.
            project_info: Optional project information to include in system prompt.

        Returns:
            List of messages including system prompt.
        """
        messages = []

        # System prompt (with project context)
        system_prompt = self.build_system_prompt(skill_names, project_info)
        messages.append({"role": "system", "content": system_prompt})

        # History
        messages.extend(history)

        # Current message (with optional image attachments)
        user_content = self._build_user_content(current_message, media)
        messages.append({"role": "user", "content": user_content})

        return messages

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """Build user message content with optional base64-encoded images."""
        if not media:
            return text
        
        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        
        if not images:
            return text
        return images + [{"type": "text", "text": text}]
    
    def add_tool_result(
        self,
        messages: list[dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        result: str
    ) -> list[dict[str, Any]]:
        """
        Add a tool result to the message list.
        
        Args:
            messages: Current message list.
            tool_call_id: ID of the tool call.
            tool_name: Name of the tool.
            result: Tool execution result.
        
        Returns:
            Updated message list.
        """
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": result
        })
        return messages
    
    def add_assistant_message(
        self,
        messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        """
        Add an assistant message to the message list.
        
        Args:
            messages: Current message list.
            content: Message content.
            tool_calls: Optional tool calls.
        
        Returns:
            Updated message list.
        """
        msg: dict[str, Any] = {"role": "assistant", "content": content or ""}
        
        if tool_calls:
            msg["tool_calls"] = tool_calls
        
        messages.append(msg)
        return messages
