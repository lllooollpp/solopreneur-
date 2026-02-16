"""
统一的会话管理器
替代分散的全局变量，提供一致的会话管理接口
"""
from typing import Dict, List, Optional
from datetime import datetime
from threading import Lock
from collections import OrderedDict
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    """聊天消息"""
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Session:
    """会话"""
    session_id: str
    messages: List[ChatMessage] = field(default_factory=list)
    system_prompt: str = ""
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def add_message(self, role: str, content: str):
        """添加消息"""
        self.messages.append(ChatMessage(role=role, content=content))
        self.updated_at = datetime.now()

    def to_messages(self) -> List[Dict]:
        """转换�?LLM 消息格式"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.extend([
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ])
        return messages

    def truncate(self, max_messages: int):
        """截断消息历史（保留最近的 max_messages 条）"""
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]


class SessionCache:
    """
    会话缓存（LRU 策略�?    线程安全的会话管理器
    """

    def __init__(self, max_size: int = 100, max_history: int = 20):
        self._sessions: OrderedDict[str, Session] = OrderedDict()
        self._lock = Lock()
        self._max_size = max_size
        self._max_history = max_history

    def get_or_create(
        self,
        session_id: str,
        system_prompt: str = "",
        metadata: Optional[Dict] = None
    ) -> Session:
        """获取或创建会�?""
        with self._lock:
            if session_id in self._sessions:
                # LRU: 移到最�?                session = self._sessions.pop(session_id)
                self._sessions[session_id] = session
                return session

            # 创建新会�?            session = Session(
                session_id=session_id,
                system_prompt=system_prompt,
                metadata=metadata or {}
            )
            self._sessions[session_id] = session

            # 超过最大容量时移除最旧的
            if len(self._sessions) > self._max_size:
                self._sessions.popitem(last=False)

            return session

    def get(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions.pop(session_id)
                self._sessions[session_id] = session
                return session
            return None

    def delete(self, session_id: str) -> bool:
        """删除会话"""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def clear(self):
        """清空所有会�?""
        with self._lock:
            self._sessions.clear()

    def list_sessions(self) -> List[Session]:
        """列出所有会�?""
        with self._lock:
            return list(self._sessions.values())

    def update_system_prompt(self, session_id: str, system_prompt: str) -> bool:
        """更新会话的系统提示词"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].system_prompt = system_prompt
                return True
            return False

    @property
    def size(self) -> int:
        """获取当前会话数量"""
        return len(self._sessions)


# 全局会话缓存实例
_global_cache: Optional[SessionCache] = None
_cache_lock = Lock()


def get_session_cache(
    max_size: int = 100,
    max_history: int = 20,
    force_new: bool = False
) -> SessionCache:
    """
    获取全局会话缓存实例

    Args:
        max_size: 最大缓存会话数
        max_history: 每个会话最大消息数
        force_new: 强制创建新实�?
    Returns:
        SessionCache 实例
    """
    global _global_cache

    if force_new:
        with _cache_lock:
            _global_cache = None

    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = SessionCache(max_size, max_history)

    return _global_cache


def reset_session_cache():
    """重置全局会话缓存"""
    global _global_cache
    with _cache_lock:
        _global_cache = None
