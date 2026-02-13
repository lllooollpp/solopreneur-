"""Session management for conversation history."""

import hashlib
import secrets
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from loguru import logger

from nanobot.storage import AppKVPersistence, SessionPersistence


# 用于session签名的密钥（应该从环境变量或配置文件加载）
_SESSION_SECRET = None
_KV_KEY_SESSION_SECRET = "session_secret"


def _get_session_secret() -> str:
    """获取或生成 session 密钥（存储于 SQLite KV）。"""
    global _SESSION_SECRET
    if _SESSION_SECRET is None:
        kv_store = AppKVPersistence()
        saved = kv_store.get(_KV_KEY_SESSION_SECRET)
        if saved:
            _SESSION_SECRET = saved
        else:
            _SESSION_SECRET = secrets.token_hex(32)
            kv_store.set(_KV_KEY_SESSION_SECRET, _SESSION_SECRET)
    return _SESSION_SECRET


def _generate_session_signature(key: str, created_at: str) -> str:
    """生成会话签名。"""
    secret = _get_session_secret()
    data = f"{key}:{created_at}:{secret}"
    return hashlib.sha256(data.encode()).hexdigest()


def _verify_session_signature(key: str, created_at: str, signature: str) -> bool:
    """验证会话签名。"""
    expected = _generate_session_signature(key, created_at)
    return secrets.compare_digest(expected, signature)


@dataclass
class Session:
    """
    A conversation session.
    
    Stores messages in SQLite-backed persistence.
    """
    
    key: str  # channel:chat_id
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    signature: str = ""  # 会话签名，防止伪造
    
    def __post_init__(self):
        """初始化后生成签名（如果未提供）。"""
        if not self.signature:
            created_at_str = self.created_at.isoformat()
            self.signature = _generate_session_signature(self.key, created_at_str)
    
    def verify_signature(self) -> bool:
        """验证会话签名是否有效。"""
        created_at_str = self.created_at.isoformat()
        return _verify_session_signature(self.key, created_at_str, self.signature)
    
    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()
    
    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """
        Get message history for LLM context.
        
        Args:
            max_messages: Maximum messages to return.
        
        Returns:
            List of messages in LLM format.
        """
        # Get recent messages
        recent = self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        
        # Convert to LLM format (just role and content)
        return [{"role": m["role"], "content": m["content"]} for m in recent]
    
    def clear(self) -> None:
        """Clear all messages in the session."""
        self.messages = []
        self.updated_at = datetime.now()


class SessionManager:
    """
    Manages conversation sessions.
    
    Sessions are stored in SQLite.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.storage = SessionPersistence()
        self._cache: dict[str, Session] = {}
        self._access_order: list[str] = []  # LRU 访问顺序
        self._max_cache_size: int = 1000  # 最大缓存数量
    
    def get_or_create(self, key: str) -> Session:
        """
        Get an existing session or create a new one.
        
        Args:
            key: Session key (usually channel:chat_id).
        
        Returns:
            The session.
        """
        # Check cache
        if key in self._cache:
            session = self._cache[key]
            # 验证缓存的会话签名
            if not session.verify_signature():
                logger.warning(f"Invalid session signature for {key}, creating new session")
                del self._cache[key]
                session = Session(key=key)
                self._cache[key] = session
            return session
        
        # Try to load from persistence
        session = self._load(key)
        if session is None:
            session = Session(key=key)
        else:
            # 验证加载的会话签名
            if not session.verify_signature():
                logger.warning(f"Invalid session signature for {key}, creating new session")
                session = Session(key=key)
        
        self._cache[key] = session
        self._update_access_order(key)
        self._evict_if_needed()
        return session
    
    def _load(self, key: str) -> Session | None:
        """Load a session from SQLite."""
        try:
            payload = self.storage.load(key)
            if payload:
                return Session(
                    key=payload["key"],
                    messages=payload.get("messages", []),
                    created_at=datetime.fromisoformat(payload["created_at"]),
                    updated_at=datetime.fromisoformat(payload["updated_at"]),
                    metadata=payload.get("metadata", {}),
                    signature=payload.get("signature", ""),
                )
        except Exception as e:
            logger.warning(f"Failed to load session {key} from SQLite: {e}")
            return None

    def _update_access_order(self, key: str) -> None:
        """更新LRU访问顺序，将key移到最前面。"""
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)

    def _evict_if_needed(self) -> None:
        """如果缓存超过最大容量，淘汰最久未使用的会话。"""
        while len(self._cache) > self._max_cache_size and self._access_order:
            oldest_key = self._access_order.pop(0)
            session = self._cache.pop(oldest_key, None)
            if session:
                self.save(session)
                logger.debug(f"Evicted session from cache: {oldest_key}")

    def save(self, session: Session) -> None:
        """Save a session to SQLite."""
        self.storage.save(
            key=session.key,
            signature=session.signature,
            metadata=session.metadata,
            created_at=session.created_at,
            updated_at=session.updated_at,
            messages=session.messages,
        )

        self._cache[session.key] = session
    
    def delete(self, key: str) -> bool:
        """
        Delete a session.
        
        Args:
            key: Session key.
        
        Returns:
            True if deleted, False if not found.
        """
        # Remove from cache
        self._cache.pop(key, None)
        
        # Remove from SQLite
        deleted = self.storage.delete(key)
        return deleted
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions.
        
        Returns:
            List of session info dicts.
        """
        try:
            sessions = self.storage.list()
            return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)
        except Exception as e:
            logger.warning(f"Failed to list sessions from SQLite: {e}")
            return []
