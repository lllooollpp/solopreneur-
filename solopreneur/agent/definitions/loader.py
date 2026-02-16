"""
Agent Configuration Loader

Loads agent definitions from YAML/JSON files.
"""

import json
import yaml
from pathlib import Path
from typing import Any
from loguru import logger

from solopreneur.agent.definitions.definition import AgentDefinition


class AgentLoader:
    """
    Loads agent definitions from configuration files.
    
    Supports YAML and JSON formats.
    """
    
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self._cache: dict[str, AgentDefinition] = {}
        
    def load(self, name: str) -> AgentDefinition | None:
        """Load a single agent by name."""
        if name in self._cache:
            return self._cache[name]
            
        # Try YAML first, then JSON
        for ext in [".yaml", ".yml", ".json"]:
            file_path = self.directory / f"{name}{ext}"
            if file_path.exists():
                return self._load_file(file_path)
        
        return None
    
    def load_all(self) -> dict[str, AgentDefinition]:
        """Load all agents from directory."""
        agents = {}
        
        if not self.directory.exists():
            return agents
            
        for file_path in self.directory.iterdir():
            if file_path.suffix in [".yaml", ".yml", ".json"]:
                try:
                    agent = self._load_file(file_path)
                    if agent:
                        agents[agent.name] = agent
                except Exception as e:
                    logger.error(f"Failed to load agent from {file_path}: {e}")
                    
        return agents
    
    def _load_file(self, file_path: Path) -> AgentDefinition | None:
        """Load agent from a single file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                if file_path.suffix == ".json":
                    data = json.load(f)
                else:
                    data = yaml.safe_load(f)
            
            if not data:
                return None
                
            # Handle inheritance
            agent = self._resolve_inheritance(data)
            
            # Cache and return
            self._cache[agent.name] = agent
            return agent
            
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
            return None
    
    def _resolve_inheritance(self, data: dict[str, Any]) -> AgentDefinition:
        """Resolve agent inheritance."""
        parent_name = data.get("extends")
        
        if parent_name:
            parent = self.load(parent_name)
            if parent:
                # Merge parent with child (child values override)
                parent_dict = parent.model_dump()
                parent_dict.update(data)
                return AgentDefinition(**parent_dict)
            else:
                logger.warning(f"Parent agent '{parent_name}' not found for '{data.get('name')}'")
        
        return AgentDefinition(**data)
    
    def clear_cache(self):
        """Clear the load cache."""
        self._cache.clear()
    
    def reload(self, name: str) -> AgentDefinition | None:
        """Reload an agent (bypass cache)."""
        if name in self._cache:
            del self._cache[name]
        return self.load(name)
