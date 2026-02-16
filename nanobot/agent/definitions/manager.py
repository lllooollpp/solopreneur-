"""
Agent Manager

High-level manager for agent operations, replacing RoleManager.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from nanobot.agent.definitions.definition import AgentDefinition
from nanobot.agent.definitions.registry import AgentRegistry

if TYPE_CHECKING:
    from nanobot.agent.core.skills import SkillsLoader


class AgentManager:
    """
    Manager for configurable agents.
    
    Replaces RoleManager with a more flexible, domain-agnostic system.
    """
    
    def __init__(self, workspace: Path, skills_loader: "SkillsLoader | None" = None):
        self.workspace = workspace
        self._skills_loader = skills_loader
        self._registry = AgentRegistry(workspace)
    
    @property
    def registry(self) -> AgentRegistry:
        """Access the agent registry."""
        return self._registry
    
    @property
    def skills(self) -> "SkillsLoader":
        """Lazy load SkillsLoader."""
        if self._skills_loader is None:
            from nanobot.agent.core.skills import SkillsLoader
            self._skills_loader = SkillsLoader(self.workspace)
        return self._skills_loader
    
    # ── Agent Query Methods ──────────────────────────────────────────────
    
    def get_agent(self, name: str) -> AgentDefinition | None:
        """Get agent by name."""
        return self._registry.get(name)
    
    def list_agents(self) -> list[AgentDefinition]:
        """List all available agents."""
        return self._registry.list_all()
    
    def list_domains(self) -> dict[str, list[AgentDefinition]]:
        """List agents grouped by domain."""
        return self._registry.list_by_domain()
    
    def get_agent_names(self) -> list[str]:
        """Get all agent names."""
        return self._registry.get_names()
    
    # ── Context Building ─────────────────────────────────────────────────
    
    def build_agent_summary(self) -> str:
        """
        Build summary of available agents for master agent context.

        This tells the master agent which sub-agents are available for delegation.
        """
        lines = [
            "# Available Agents",
            "",
            "Prefer `delegate_auto` to let system analyze dependencies and choose serial/parallel execution automatically.",
            "Use `delegate` only when you explicitly need strict sequential handoff.",
            "Use `delegate_parallel` only when you are certain tasks are independent.",
            "",
        ]

        domains = self.list_domains()
        for domain, agents in sorted(domains.items()):
            lines.append(f"## {domain.title()}")
            for agent in agents:
                source_tag = "[custom]" if agent.metadata.get("source") == "custom" else ""
                lines.append(
                    f"- **{agent.emoji} {agent.title}** (`{agent.name}`) "
                    f"{source_tag} - {agent.description}"
                )
            lines.append("")

        lines.extend([
            "## Usage",
            "",
            "Use `delegate_auto` for mixed orchestration (recommended):",
            '```yaml',
            'jobs:',
            '  - id: "backend"',
            '    agent: "developer"',
            '    task: "Implement backend API"',
            '  - id: "frontend"',
            '    agent: "developer"',
            '    task: "Build frontend page"',
            '  - id: "integration_test"',
            '    agent: "tester"',
            '    task: "Run integration tests"',
            '    depends_on: ["backend", "frontend"]',
            'max_parallel: 3',
            '```',
            "",
            "Use `delegate` to assign a task to a specific agent and get the result synchronously:",
            '```yaml',
            'agent: "developer"',
            'task: "Implement the login API endpoint"',
            'context: "<output from previous agent>"  # optional',
            'project_dir: "/path/to/project"          # optional',
            '```',
            "",
            "Chain multiple `delegate` calls to orchestrate complex tasks. Pass each agent's output as `context` to the next.",
            "Use `delegate_parallel` when tasks are independent and can run concurrently.",
            "",
            "> `run_workflow` is also available as a shortcut for standard multi-agent pipelines when the user explicitly requests it.",
        ])

        return "\n".join(lines)
    
    def build_agent_prompt(
        self,
        agent: AgentDefinition,
        task: str,
        context: str = "",
        project_dir: str = ""
    ) -> str:
        """
        Build complete system prompt for an agent.
        
        Args:
            agent: The agent definition
            task: The task to perform
            context: Previous step output (for workflows)
            project_dir: Project directory path
        
        Returns:
            Complete system prompt
        """
        parts = [agent.system_prompt]
        
        # Load skills
        if agent.skills:
            skill_content = self.skills.load_skills_for_context(agent.skills)
            if skill_content:
                parts.append(f"\n\n# Reference Skills\n\n{skill_content}")
        
        # Workspace info
        workspace_path = str(self.workspace.expanduser().resolve())
        parts.append(f"\n\n# Workspace\n\nYour workspace: {workspace_path}")
        
        # Project directory
        if project_dir:
            parts.append(
                f"\n\n# Project Directory\n\n"
                f"All files must be created under: {project_dir}\n\n"
                f"**Rules:**\n"
                f"- Use `write_file` with paths relative to this directory\n"
                f"- Create actual files, not just describe code\n"
                f"- Each source file must be written via `write_file`"
            )
        
        # Upstream context (for workflows)
        if context:
            parts.append(
                f"\n\n# Previous Work Output\n\n"
                f"Continue based on this previous work:\n\n{context}"
            )
        
        # Output format
        if agent.output_format:
            parts.append(f"\n\n# Output Format\n\n{agent.output_format}")
        
        # Task
        parts.append(
            f"\n\n# Current Task\n\n"
            f"Act as **{agent.title}** to complete this task:\n\n{task}"
        )
        
        return "\n".join(parts)
    
    def build_agent_messages(
        self,
        agent: AgentDefinition,
        task: str,
        context: str = "",
        project_dir: str = ""
    ) -> list[dict[str, Any]]:
        """
        Build complete message list for an agent.
        
        Returns:
            LLM message list
        """
        system_prompt = self.build_agent_prompt(agent, task, context, project_dir)
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]
    
    # ── CRUD Operations ───────────────────────────────────────────────────
    
    def create_agent(self, agent: AgentDefinition) -> bool:
        """Create a new custom agent."""
        return self._registry.create_custom(agent)
    
    def update_agent(self, name: str, updates: dict[str, Any]) -> bool:
        """
        Update an existing agent.
        
        For preset agents, this creates a custom override.
        For custom agents, this updates the existing file.
        
        Args:
            name: Agent name to update
            updates: Dictionary of fields to update
            
        Returns:
            True if successful
        """
        existing = self._registry.get(name)
        if not existing:
            return False
        
        # Merge existing with updates
        agent_dict = existing.model_dump()
        agent_dict.update(updates)
        
        # Ensure metadata reflects this is now a custom agent
        agent_dict["metadata"] = {**existing.metadata, "source": "custom"}
        
        updated_agent = AgentDefinition(**agent_dict)
        
        # If it was a preset, create new custom; if custom, update existing
        if existing.metadata.get("source") == "preset":
            return self._registry.create_custom(updated_agent)
        else:
            # Delete old version and create new
            self._registry.delete_custom(name)
            return self._registry.create_custom(updated_agent)
    
    def delete_agent(self, name: str) -> bool:
        """
        Delete an agent.
        
        For preset agents, this creates a 'disabled' marker in custom.
        For custom agents, this deletes the file.
        """
        return self._registry.delete_custom(name)
    
    def reload(self):
        """Reload all agents."""
        self._registry.reload()
