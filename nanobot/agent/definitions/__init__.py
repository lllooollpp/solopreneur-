"""
Agent definitions module - Configuration system.

This module provides a fully configurable agent system where agents
can be defined via YAML/JSON configuration files, supporting any domain
(software engineering, medical, legal, etc.)
"""

from nanobot.agent.definitions.definition import AgentDefinition, AgentType
from nanobot.agent.definitions.loader import AgentLoader
from nanobot.agent.definitions.registry import AgentRegistry
from nanobot.agent.definitions.manager import AgentManager

__all__ = [
    "AgentDefinition",
    "AgentType",
    "AgentLoader",
    "AgentRegistry",
    "AgentManager",
]
