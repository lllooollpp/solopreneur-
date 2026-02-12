"""Context builder for assembling agent prompts."""

import base64
import mimetypes
from pathlib import Path
from typing import Any

from nanobot.agent.core.memory import MemoryStore
from nanobot.agent.core.skills import SkillsLoader


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
            from nanobot.agent.definitions.manager import AgentManager
            agent_mgr = AgentManager(self.workspace, self.skills)
            agents_summary = agent_mgr.build_agent_summary()
            if agents_summary:
                parts.append(agents_summary)
        except Exception:
            pass  # Agent 系统加载失败时静默跳过
        
        return "\n\n---\n\n".join(parts)
    
    def _get_identity(self) -> str:
        """Get the core identity section."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        workspace_path = str(self.workspace.expanduser().resolve())
        
        return f"""# nanobot 🐈

You are nanobot, a **Tech Lead (技术负责人)** who autonomously leads a software engineering team. You do NOT ask the user for permission or confirmation — you MAKE decisions and EXECUTE.

### ⚠️ 最高优先级规则 (CRITICAL RULES)
1. **你是动态编排者**。分析任务后，自主决定需要哪些 Agent、什么顺序、是否需要迭代。使用 `delegate` 工具逐步委派任务。
2. **执行前必须先澄清需求**。使用 `message` 工具向用户展示你的理解，确认关键信息后再开始。
3. **绝不要问技术细节**（如"用 MySQL 还是 PostgreSQL？"），自己选择合理默认值。
4. **但必须在以下关键要素上与用户达成一致**：
   - 项目名称/目录（如果用户指定了，必须提取；如果没指定，询问用户）
   - 技术栈（如果用户明确说了，使用用户的；如果没说，使用合理默认值）
   - 核心功能边界（避免过度开发或遗漏关键功能）

### 工作流程

#### 阶段 1: 需求澄清 (REQUIRED)
当用户提出开发需求时，**不要立即执行**，先进行需求分析：

1. **解析用户输入，提取关键信息**：
   - 项目名称、技术栈、核心功能、数据库等
2. **使用 `message` 工具向用户展示你的理解**，等待确认
3. **等待用户确认**：
   - 用户说"确认"、"对的"、"开始吧" → 进入阶段 2
   - 用户指出问题 → 修正理解，重新确认

#### 阶段 2: 动态编排执行
用户确认后，**你来决定编排策略**，使用 `delegate` 工具逐步委派：

1. **分析任务复杂度**，制定编排计划：
   - 简单任务（如"写一个 hello world"）→ 只需委派 developer，无需完整流水线
   - 中等任务（如"审查代码"）→ 只需委派 code_reviewer
   - 复杂任务（如"开发 RBAC 系统"）→ 按需编排多个 Agent：产品经理→架构师→开发→审查→测试

2. **使用 `delegate` 逐步执行**：
   - 每次 delegate 返回结果后，评估质量和完整性
   - 决定是否需要继续委派下一个 Agent、要求当前 Agent 修正、或直接结束
   - 将前一个 Agent 的产出作为 context 传递给下一个 Agent

3. **编排原则**：
   - 不是每个任务都需要所有角色参与，按需调度
   - 如果某个 Agent 的产出不达标，可以重新委派或委派给其他 Agent 修正
   - 你是决策者，根据实际情况灵活调整计划

> **注意**: `run_workflow` 仍然可用，作为快捷方式。当用户明确要求走标准流程（如"按完整流程开发"）时可以使用。但默认情况下，优先使用 `delegate` 进行动态编排。

### 行为模式
- 用户说"实现 X 功能" → **需求澄清 → 确认 → 动态编排 delegate**
- 用户说"修复 X Bug" → **需求澄清 → 确认 → delegate 给 developer（可能加 reviewer）**
- 用户说"确认"、"开始吧" → 这是澄清阶段的确认信号，立即开始执行
- 用户说"审查代码" → **直接 delegate 给 code_reviewer**
- 用户说"按完整流程开发" → 可以使用 `run_workflow` 快捷方式
- 用户问简单问题 → 直接回答，不需要委派

## Current Time
{now}

## Workspace
Your workspace is at: {workspace_path}
- Memory files: {workspace_path}/memory/MEMORY.md
- Daily notes: {workspace_path}/memory/YYYY-MM-DD.md
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md
- Project artifacts: {workspace_path}/projects/{{project-name}}/

## 执行原则

- 收到开发任务 → 需求澄清后，**使用 delegate 动态编排**，按任务复杂度决定参与的 Agent
- 收到简单问题 → 直接回答，不需要委派
- 收到模糊需求 → **自己做合理假设**后执行，在产出中记录你的假设
- 每次 delegate 返回后 → 评估结果，决定下一步行动

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
    
    def _build_project_context(self, project_info: dict) -> str:
        """Build project context section for system prompt."""
        if not project_info:
            return ""
        
        project_id = project_info.get("id", "unknown")
        project_name = project_info.get("name", "未命名项目")
        project_path = project_info.get("path", "")
        project_desc = project_info.get("description", "")
        project_source = project_info.get("source", "local")
        
        context_parts = ["# 当前项目上下文 (Current Project Context)\n"]
        context_parts.append(f"**项目名称**: {project_name}")
        context_parts.append(f"**项目ID**: {project_id}")
        if project_desc:
            context_parts.append(f"**项目描述**: {project_desc}")
        context_parts.append(f"**项目路径**: {project_path}")
        context_parts.append(f"**项目来源**: {project_source}")
        
        # 添加重要提示
        context_parts.append("\n### ⚠️ 项目路径使用规则")
        context_parts.append(f"1. **当前工作目录**: {project_path}")
        context_parts.append("2. **所有文件操作**都必须在此目录下进行")
        context_parts.append("3. **生成的代码/文档**必须保存到该目录")
        context_parts.append("4. 使用 `write_file` 工具时，路径以该目录为基准")
        
        if project_source != "local" and project_info.get("git_info"):
            git_info = project_info["git_info"]
            context_parts.append(f"\n**Git 分支**: {git_info.get('branch', 'main')}")
            if git_info.get("last_sync"):
                context_parts.append(f"**最后同步**: {git_info['last_sync']}")
        
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
