"""Domain-oriented persistence services built on top of SQLiteStore."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from nanobot.storage.sqlite_store import SQLiteStore


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
