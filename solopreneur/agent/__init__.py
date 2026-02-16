"""Agent module - Core runtime and definitions."""

# Re-export from core (runtime components)
from solopreneur.agent.core.loop import AgentLoop
from solopreneur.agent.core.context import ContextBuilder
from solopreneur.agent.core.memory import MemoryStore
from solopreneur.agent.core.skills import SkillsLoader
from solopreneur.agent.core.subagent import SubagentManager
from solopreneur.agent.core.compaction import CompactionEngine

# Re-export from definitions (configuration system)
from solopreneur.agent.definitions.definition import AgentDefinition, AgentType
from solopreneur.agent.definitions.loader import AgentLoader
from solopreneur.agent.definitions.registry import AgentRegistry
from solopreneur.agent.definitions.manager import AgentManager

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
