"""
Agent Registry

Central registry for all agents (built-in presets + user custom).
"""

from pathlib import Path
from typing import Any
from loguru import logger

from nanobot.agents.definition import AgentDefinition
from nanobot.agents.loader import AgentLoader


class AgentRegistry:
    """
    Registry for all available agents.
    
    Manages both built-in preset agents and user-defined custom agents.
    Custom agents take precedence over presets.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        
        # Built-in preset agents
        preset_dir = Path(__file__).parent / "presets"
        self._preset_loader = AgentLoader(preset_dir)
        
        # User custom agents (workspace/agents/)
        custom_dir = workspace / "agents"
        self._custom_loader = AgentLoader(custom_dir)
        
        # Cache all loaded agents
        self._agents: dict[str, AgentDefinition] = {}
        self._load_all()
    
    def _load_all(self):
        """Load all agents (presets first, then custom overrides)."""
        # Load presets from all subdirectories
        preset_dir = Path(__file__).parent / "presets"
        for domain_dir in preset_dir.iterdir():
            if domain_dir.is_dir():
                loader = AgentLoader(domain_dir)
                for name, agent in loader.load_all().items():
                    # Prefix preset agents with domain
                    agent.metadata["domain"] = domain_dir.name
                    agent.metadata["source"] = "preset"
                    self._agents[name] = agent
        
        # Load custom agents (override presets)
        for name, agent in self._custom_loader.load_all().items():
            agent.metadata["domain"] = agent.metadata.get("domain", "custom")
            agent.metadata["source"] = "custom"
            self._agents[name] = agent
            if name in self._agents and self._agents[name].metadata.get("source") == "preset":
                logger.info(f"Custom agent '{name}' overrides preset")
        
        logger.info(f"Loaded {len(self._agents)} agents: "
                   f"{sum(1 for a in self._agents.values() if a.metadata.get('source') == 'preset')} preset, "
                   f"{sum(1 for a in self._agents.values() if a.metadata.get('source') == 'custom')} custom")
    
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
        self._agents.clear()
        self._preset_loader.clear_cache()
        self._custom_loader.clear_cache()
        self._load_all()
    
    def create_custom(self, agent: AgentDefinition) -> bool:
        """Create a new custom agent."""
        custom_dir = self.workspace / "agents"
        custom_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = custom_dir / f"{agent.name}.yaml"
        
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
        custom_dir = self.workspace / "agents"
        
        for ext in [".yaml", ".yml", ".json"]:
            file_path = custom_dir / f"{name}{ext}"
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.reload()
                    return True
                except Exception as e:
                    logger.error(f"Failed to delete agent: {e}")
                    return False
        
        return False
