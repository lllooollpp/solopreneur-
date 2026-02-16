"""
Agent definitions module - Configuration system.

This module provides a fully configurable agent system where agents
can be defined via YAML/JSON configuration files, supporting any domain
(software engineering, medical, legal, etc.)
"""

from solopreneur.agent.definitions.definition import AgentDefinition, AgentType
from solopreneur.agent.definitions.loader import AgentLoader
from solopreneur.agent.definitions.registry import AgentRegistry
from solopreneur.agent.definitions.manager import AgentManager

__all__ = [
    "AgentDefinition",
    "AgentType",
    "AgentLoader",
    "AgentRegistry",
    "AgentManager",
]
