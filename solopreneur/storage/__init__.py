"""Storage backends for solopreneur."""

from solopreneur.storage.sqlite_store import SQLiteStore
from solopreneur.storage.services import (
	AppKVPersistence,
	GitCredentialPersistence,
	ProjectPersistence,
	SessionPersistence,
	SubagentTaskPersistence,
	UsagePersistence,
)

__all__ = [
	"SQLiteStore",
	"AppKVPersistence",
	"GitCredentialPersistence",
	"SessionPersistence",
	"ProjectPersistence",
	"UsagePersistence",
	"SubagentTaskPersistence",
]

# Lazy import for memory engine (avoid import overhead when not used)
def get_memory_search_engine():
	"""Lazy factory for MemorySearchEngine."""
	from solopreneur.storage.memory_engine.engine import MemorySearchEngine
	return MemorySearchEngine
