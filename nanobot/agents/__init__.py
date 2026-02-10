"""
Configurable Agent System

This module provides a fully configurable agent system where agents
can be defined via YAML/JSON configuration files, supporting any domain
(software engineering, medical, legal, etc.)
"""

from nanobot.agents.definition import AgentDefinition, AgentType
from nanobot.agents.loader import AgentLoader
from nanobot.agents.registry import AgentRegistry
from nanobot.agents.manager import AgentManager

__all__ = [
    "AgentDefinition",
    "AgentType",
    "AgentLoader",
    "AgentRegistry",
    "AgentManager",
]
