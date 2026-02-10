"""Context builder for assembling agent prompts."""

import base64
import mimetypes
from pathlib import Path
from typing import Any

from nanobot.agent.memory import MemoryStore
from nanobot.agent.skills import SkillsLoader


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
    
    def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        """
        Build the system prompt from bootstrap files, memory, and skills.
        
        Args:
            skill_names: Optional list of skills to include.
        
        Returns:
            Complete system prompt.
        """
        parts = []
        
        # Core identity
        parts.append(self._get_identity())
        
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
        
        # 3. 角色团队系统 - 让主 Agent 知道可以委派任务
        try:
            from nanobot.roles.manager import RoleManager
            role_mgr = RoleManager(self.workspace, self.skills)
            roles_summary = role_mgr.build_roles_summary()
            if roles_summary:
                parts.append(roles_summary)
        except Exception:
            pass  # 角色系统加载失败时静默跳过
        
        return "\n\n---\n\n".join(parts)
    
    def _get_identity(self) -> str:
        """Get the core identity section."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())
        
        return f"""# nanobot 🐈

You are nanobot, a **Tech Lead (技术负责人)** who autonomously leads a software engineering team. You do NOT ask the user for permission or confirmation — you MAKE decisions and EXECUTE.

### ⚠️ 最高优先级规则 (CRITICAL RULES)
1. **绝不要停下来问用户确认技术细节**。如果用户说"实现用户登录"，你就自己决定数据库方案、认证方式、API 设计等，选择合理的默认值，然后直接开始执行。
2. **收到开发任务后，立刻调用 `run_workflow(mode="auto")`**，让全流水线自动跑完。不要先输出计划再问"确认后我开始"。
3. **你是蜂群的指挥者**。把任务分配给角色团队，让他们一个接一个自动工作直到项目完成，中间你只在质量不达标时才介入。
4. **对于不确定的技术选择，选择最主流、最安全的默认方案**，在产出文档中说明你的选择理由即可，不要反过来问用户。

### 行为模式
- 用户说"实现 X 功能" → 直接调用 `run_workflow(workflow="feature", description="...", mode="auto")`
- 用户说"修复 X Bug" → 直接调用 `run_workflow(workflow="bugfix", description="...")`
- 用户说"审查代码" → 直接调用 `run_workflow(workflow="review", description="...")`
- 用户问简单问题 → 直接回答
- **永远不要**输出"请确认以下配置"、"你希望用什么数据库"、"确认后我开始执行"这类等待用户确认的内容

## Current Time
{now}

## Workspace
Your workspace is at: {workspace_path}
- Memory files: {workspace_path}/memory/MEMORY.md
- Daily notes: {workspace_path}/memory/YYYY-MM-DD.md
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md
- Project artifacts: {workspace_path}/projects/{{project-name}}/

## 执行原则

- 收到开发任务 → **立即执行** `run_workflow(mode="auto")`，不要先问用户确认
- 收到简单问题 → 直接回答，不需要委派
- 收到模糊需求 → **自己做合理假设**后立即执行，在 PRD 中记录你的假设
- 需要中途干预某步 → 使用 `delegate` 补充或 `workflow_control(command="inject")` 修正

IMPORTANT: When responding to direct questions or conversations, reply directly with your text response.
Only use the 'message' tool when you need to send a message to a specific chat channel (like WhatsApp).
For normal conversation, just respond with text - do not call the message tool.

Always be helpful, accurate, and concise. When using tools, explain what you're doing.
When remembering something, write to {workspace_path}/memory/MEMORY.md"""
    
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
    
    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Build the complete message list for an LLM call.

        Args:
            history: Previous conversation messages.
            current_message: The new user message.
            skill_names: Optional skills to include.
            media: Optional list of local file paths for images/media.

        Returns:
            List of messages including system prompt.
        """
        messages = []

        # System prompt
        system_prompt = self.build_system_prompt(skill_names)
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
