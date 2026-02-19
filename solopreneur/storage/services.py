"""Domain-oriented persistence services built on top of SQLiteStore."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from solopreneur.storage.sqlite_store import SQLiteStore


class SessionPersistence:
    """Persistence service for sessions and messages."""

    def __init__(self, store: SQLiteStore | None = None):
        self._store = store or SQLiteStore()

    def load(self, key: str) -> dict[str, Any] | None:
        return self._store.load_session(key)

    def save(
        self,
        key: str,
        signature: str,
        metadata: dict[str, Any],
        created_at: datetime,
        updated_at: datetime,
        messages: list[dict[str, Any]],
    ) -> None:
        self._store.save_session(
            key=key,
            signature=signature,
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at,
            messages=messages,
        )

    def delete(self, key: str) -> bool:
        return self._store.delete_session(key)

    def list(self) -> list[dict[str, Any]]:
        return self._store.list_sessions()


class ProjectPersistence:
    """Persistence service for project metadata."""

    def __init__(self, store: SQLiteStore | None = None, db_path: Path | None = None):
        self._store = store or SQLiteStore(db_path)

    def load_all(self) -> list[dict[str, Any]]:
        return self._store.load_all_projects()

    def save(self, project_data: dict[str, Any]) -> None:
        self._store.save_project(project_data)

    def delete(self, project_id: str) -> bool:
        return self._store.delete_project(project_id)


class UsagePersistence:
    """Persistence service for LLM usage telemetry."""

    def __init__(self, store: SQLiteStore | None = None):
        self._store = store or SQLiteStore()

    def record(
        self,
        session_key: str | None,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        duration_ms: int = 0,
        is_stream: bool = False,
    ) -> None:
        self._store.record_llm_usage(
            session_key=session_key,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            is_stream=is_stream,
        )


class SubagentTaskPersistence:
    """Persistence service for subagent task status."""

    def __init__(self, store: SQLiteStore | None = None):
        self._store = store or SQLiteStore()

    def upsert(
        self,
        task_id: str,
        label: str,
        task_text: str,
        origin_channel: str,
        origin_chat_id: str,
        status: str,
        result_text: str | None = None,
        error_text: str | None = None,
    ) -> None:
        self._store.upsert_subagent_task(
            task_id=task_id,
            label=label,
            task_text=task_text,
            origin_channel=origin_channel,
            origin_chat_id=origin_chat_id,
            status=status,
            result_text=result_text,
            error_text=error_text,
        )


class AppKVPersistence:
    """Persistence service for application key-value settings."""

    def __init__(self, store: SQLiteStore | None = None):
        self._store = store or SQLiteStore()

    def get(self, key: str) -> str | None:
        return self._store.get_kv(key)

    def set(self, key: str, value: str) -> None:
        self._store.set_kv(key, value)

    def delete(self, key: str) -> bool:
        return self._store.delete_kv(key)


class GitCredentialPersistence:
    """Persistence service for git credentials."""

    def __init__(self, store: SQLiteStore | None = None, db_path: Path | None = None):
        self._store = store or SQLiteStore(db_path)

    def get(self, project_id: str) -> tuple[str | None, str | None]:
        return self._store.get_git_credentials(project_id)

    def set(self, project_id: str, username: str | None, token: str | None) -> None:
        self._store.set_git_credentials(project_id, username, token)

    def delete(self, project_id: str) -> bool:
        return self._store.delete_git_credentials(project_id)


class TracePersistence:
    """Persistence service for trace events (audit trail)."""

    def __init__(self, store: SQLiteStore | None = None):
        self._store = store or SQLiteStore()

    def save_event(
        self,
        session_key: str,
        request_id: str,
        event_type: str,
        data: dict[str, Any],
        project_id: str | None = None,
        agent_name: str | None = None,
    ) -> None:
        self._store.save_trace_event(
            session_key=session_key,
            request_id=request_id,
            event_type=event_type,
            data=data,
            project_id=project_id,
            agent_name=agent_name,
        )

    def save_batch(self, events: list[dict[str, Any]]) -> None:
        self._store.save_trace_events_batch(events)

    def load(
        self,
        session_key: str,
        request_id: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return self._store.load_trace_events(
            session_key=session_key,
            request_id=request_id,
            limit=limit,
        )

    def list_requests(self, session_key: str) -> list[dict[str, Any]]:
        return self._store.list_trace_requests(session_key)

    def delete(self, session_key: str, request_id: str | None = None) -> int:
        return self._store.delete_trace_events(session_key, request_id)
