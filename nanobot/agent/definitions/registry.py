"""
Agent Registry

Single-source registry for all agents under one canonical directory.
"""

from pathlib import Path
import shutil
from loguru import logger

from nanobot.agent.definitions.definition import AgentDefinition
from nanobot.agent.definitions.loader import AgentLoader


class AgentRegistry:
    """
    Registry for all available agents from one canonical path.
    Canonical path: <workspace>/agents
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace

        # Canonical single source directory
        self._agents_dir = workspace / "agents"
        self._agents_dir.mkdir(parents=True, exist_ok=True)

        # Bootstrap built-in presets into canonical directory (only missing files)
        self._seed_builtin_agents()

        self._loader = AgentLoader(self._agents_dir)
        
        # Cache all loaded agents
        self._agents: dict[str, AgentDefinition] = {}
        self._load_all()
    
    def _load_all(self):
        """Load all agents from canonical directory."""
        self._agents.clear()

        for name, agent in self._loader.load_all().items():
            # Ensure compatible metadata fields exist
            agent.metadata["domain"] = agent.metadata.get("domain", "general")
            agent.metadata["source"] = agent.metadata.get("source", "preset")
            self._agents[name] = agent

        logger.info(
            f"Loaded {len(self._agents)} agents from canonical path: {self._agents_dir}"
        )

    def _seed_builtin_agents(self):
        """Copy built-in preset agent files into canonical directory if missing."""
        preset_root = Path(__file__).parent / "presets"
        if not preset_root.exists():
            return

        copied = 0
        for domain_dir in preset_root.iterdir():
            if not domain_dir.is_dir():
                continue
            for file_path in domain_dir.iterdir():
                if file_path.suffix not in [".yaml", ".yml", ".json"]:
                    continue
                target = self._agents_dir / file_path.name
                if not target.exists():
                    shutil.copy2(file_path, target)
                    copied += 1

        if copied:
            logger.info(f"Bootstrapped {copied} built-in agents to {self._agents_dir}")
    
    def get(self, name: str) -> AgentDefinition | None:
        """Get agent by name."""
        return self._agents.get(name)
    
    def list_all(self) -> list[AgentDefinition]:
        """List all available agents."""
        return list(self._agents.values())
    
    def list_by_domain(self) -> dict[str, list[AgentDefinition]]:
        """List agents grouped by domain."""
        domains: dict[str, list[AgentDefinition]] = {}
        for agent in self._agents.values():
            domain = agent.metadata.get("domain", "general")
            if domain not in domains:
                domains[domain] = []
            domains[domain].append(agent)
        return domains
    
    def list_by_type(self, agent_type: str) -> list[AgentDefinition]:
        """List agents by type."""
        return [a for a in self._agents.values() if a.type.value == agent_type]
    
    def exists(self, name: str) -> bool:
        """Check if agent exists."""
        return name in self._agents
    
    def get_names(self) -> list[str]:
        """Get all agent names."""
        return list(self._agents.keys())
    
    def reload(self):
        """Reload all agents."""
        self._loader.clear_cache()
        self._load_all()
    
    def create_custom(self, agent: AgentDefinition) -> bool:
        """Create a new custom agent."""
        self._agents_dir.mkdir(parents=True, exist_ok=True)

        file_path = self._agents_dir / f"{agent.name}.yaml"
        
        try:
            import yaml
            with open(file_path, "w", encoding="utf-8") as f:
                yaml.dump(agent.model_dump(exclude_none=True), f, 
                         allow_unicode=True, sort_keys=False)
            
            # Reload
            self.reload()
            return True
        except Exception as e:
            logger.error(f"Failed to create agent: {e}")
            return False
    
    def delete_custom(self, name: str) -> bool:
        """Delete a custom agent."""
        for ext in [".yaml", ".yml", ".json"]:
            file_path = self._agents_dir / f"{name}{ext}"
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.reload()
                    return True
                except Exception as e:
                    logger.error(f"Failed to delete agent: {e}")
                    return False
        
        return False
