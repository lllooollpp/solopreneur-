"""Agent module - Core runtime and definitions."""

# Re-export from core (runtime components)
from nanobot.agent.core.loop import AgentLoop
from nanobot.agent.core.context import ContextBuilder
from nanobot.agent.core.memory import MemoryStore
from nanobot.agent.core.skills import SkillsLoader
from nanobot.agent.core.subagent import SubagentManager
from nanobot.agent.core.compaction import CompactionEngine

# Re-export from definitions (configuration system)
from nanobot.agent.definitions.definition import AgentDefinition, AgentType
from nanobot.agent.definitions.loader import AgentLoader
from nanobot.agent.definitions.registry import AgentRegistry
from nanobot.agent.definitions.manager import AgentManager

__all__ = [
    # Core
    "AgentLoop",
    "ContextBuilder",
    "MemoryStore",
    "SkillsLoader",
    "SubagentManager",
    "CompactionEngine",
    # Definitions
    "AgentDefinition",
    "AgentType",
    "AgentLoader",
    "AgentRegistry",
    "AgentManager",
]
