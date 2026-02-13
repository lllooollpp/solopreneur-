"""SQLite storage backend for session and project persistence."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from loguru import logger


class SQLiteStore:
    """Thread-safe SQLite storage backend."""

    def __init__(self, db_path: Path | None = None):
        self.data_dir = Path.home() / ".nanobot"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or (self.data_dir / "nanobot.db")
        self._lock = Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            conn.execute("PRAGMA busy_timeout=5000;")

            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    key TEXT PRIMARY KEY,
                    signature TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_key TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    timestamp TEXT NOT NULL,
                    extra_json TEXT,
                    FOREIGN KEY(session_key) REFERENCES sessions(key) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session_time
                ON messages(session_key, id);

                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
                ON sessions(updated_at);

                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    source TEXT NOT NULL,
                    path TEXT NOT NULL,
                    git_info_json TEXT,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_projects_status_updated
                ON projects(status, updated_at);

                CREATE TABLE IF NOT EXISTS llm_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_key TEXT,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    is_stream INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_llm_usage_session_time
                ON llm_usage(session_key, created_at);

                CREATE TABLE IF NOT EXISTS subagent_tasks (
                    task_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    task_text TEXT NOT NULL,
                    origin_channel TEXT NOT NULL,
                    origin_chat_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_text TEXT,
                    error_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_subagent_tasks_status_updated
                ON subagent_tasks(status, updated_at);

                CREATE TABLE IF NOT EXISTS app_kv (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS git_credentials (
                    project_id TEXT PRIMARY KEY,
                    username TEXT,
                    token TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _to_iso(value: datetime | str | None) -> str:
        if value is None:
            return datetime.now().isoformat()
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    # ---------- Session persistence ----------

    def load_session(self, key: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT key, signature, metadata_json, created_at, updated_at
                FROM sessions WHERE key = ?
                """,
                (key,),
            ).fetchone()
            if not row:
                return None

            message_rows = conn.execute(
                """
                SELECT role, content, timestamp, extra_json
                FROM messages
                WHERE session_key = ?
                ORDER BY id ASC
                """,
                (key,),
            ).fetchall()

        messages: list[dict[str, Any]] = []
        for msg in message_rows:
            payload = {
                "role": msg["role"],
                "content": msg["content"],
                "timestamp": msg["timestamp"],
            }
            if msg["extra_json"]:
                try:
                    payload.update(json.loads(msg["extra_json"]))
                except json.JSONDecodeError:
                    logger.warning(f"Invalid message extra_json in session {key}")
            messages.append(payload)

        metadata = {}
        if row["metadata_json"]:
            try:
                metadata = json.loads(row["metadata_json"])
            except json.JSONDecodeError:
                logger.warning(f"Invalid metadata_json in session {key}")

        return {
            "key": row["key"],
            "signature": row["signature"],
            "metadata": metadata,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "messages": messages,
        }

    def save_session(
        self,
        key: str,
        signature: str,
        metadata: dict[str, Any],
        created_at: datetime,
        updated_at: datetime,
        messages: list[dict[str, Any]],
    ) -> None:
        created_at_iso = self._to_iso(created_at)
        updated_at_iso = self._to_iso(updated_at)

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(key, signature, metadata_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    signature = excluded.signature,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    signature,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    created_at_iso,
                    updated_at_iso,
                ),
            )

            conn.execute("DELETE FROM messages WHERE session_key = ?", (key,))

            if messages:
                params = []
                for msg in messages:
                    role = msg.get("role", "assistant")
                    content = msg.get("content")
                    timestamp = msg.get("timestamp") or datetime.now().isoformat()
                    extras = {k: v for k, v in msg.items() if k not in {"role", "content", "timestamp"}}
                    extra_json = json.dumps(extras, ensure_ascii=False) if extras else None
                    params.append((key, role, content, timestamp, extra_json))

                conn.executemany(
                    """
                    INSERT INTO messages(session_key, role, content, timestamp, extra_json)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    params,
                )

    def delete_session(self, key: str) -> bool:
        with self._lock, self._connect() as conn:
            result = conn.execute("DELETE FROM sessions WHERE key = ?", (key,))
            return result.rowcount > 0

    def list_sessions(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT key, created_at, updated_at
                FROM sessions
                ORDER BY updated_at DESC
                """
            ).fetchall()

        return [
            {
                "key": row["key"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    # ---------- Project persistence ----------

    def load_all_projects(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, description, source, path, git_info_json,
                       session_id, status, created_at, updated_at
                FROM projects
                ORDER BY created_at DESC
                """
            ).fetchall()

        projects: list[dict[str, Any]] = []
        for row in rows:
            git_info = None
            if row["git_info_json"]:
                try:
                    git_info = json.loads(row["git_info_json"])
                except json.JSONDecodeError:
                    logger.warning(f"Invalid git_info_json in project {row['id']}")

            projects.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "description": row["description"],
                    "source": row["source"],
                    "path": row["path"],
                    "git_info": git_info,
                    "session_id": row["session_id"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return projects

    def save_project(self, project_data: dict[str, Any]) -> None:
        git_info = project_data.get("git_info")
        git_info_json = json.dumps(git_info, ensure_ascii=False) if git_info else None

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects(id, name, description, source, path, git_info_json,
                                     session_id, status, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    source = excluded.source,
                    path = excluded.path,
                    git_info_json = excluded.git_info_json,
                    session_id = excluded.session_id,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    project_data["id"],
                    project_data["name"],
                    project_data.get("description"),
                    project_data["source"],
                    project_data["path"],
                    git_info_json,
                    project_data["session_id"],
                    project_data["status"],
                    project_data["created_at"],
                    project_data["updated_at"],
                ),
            )

    def delete_project(self, project_id: str) -> bool:
        with self._lock, self._connect() as conn:
            result = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            return result.rowcount > 0

    # ---------- Usage persistence ----------

    def record_llm_usage(
        self,
        session_key: str | None,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        duration_ms: int = 0,
        is_stream: bool = False,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO llm_usage(
                    session_key, model, prompt_tokens, completion_tokens,
                    total_tokens, duration_ms, is_stream, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_key,
                    model,
                    max(int(prompt_tokens or 0), 0),
                    max(int(completion_tokens or 0), 0),
                    max(int(total_tokens or 0), 0),
                    max(int(duration_ms or 0), 0),
                    1 if is_stream else 0,
                    datetime.now().isoformat(),
                ),
            )

    # ---------- Subagent task persistence ----------

    def upsert_subagent_task(
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
        now = datetime.now().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO subagent_tasks(
                    task_id, label, task_text, origin_channel, origin_chat_id,
                    status, result_text, error_text, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    label = excluded.label,
                    task_text = excluded.task_text,
                    origin_channel = excluded.origin_channel,
                    origin_chat_id = excluded.origin_chat_id,
                    status = excluded.status,
                    result_text = excluded.result_text,
                    error_text = excluded.error_text,
                    updated_at = excluded.updated_at
                """,
                (
                    task_id,
                    label,
                    task_text,
                    origin_channel,
                    origin_chat_id,
                    status,
                    result_text,
                    error_text,
                    now,
                    now,
                ),
            )

    # ---------- Generic KV persistence ----------

    def get_kv(self, key: str) -> str | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_kv WHERE key = ?",
                (key,),
            ).fetchone()
            return row["value"] if row else None

    def set_kv(self, key: str, value: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_kv(key, value, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, datetime.now().isoformat()),
            )

    def delete_kv(self, key: str) -> bool:
        with self._lock, self._connect() as conn:
            result = conn.execute("DELETE FROM app_kv WHERE key = ?", (key,))
            return result.rowcount > 0

    # ---------- Git credential persistence ----------

    def get_git_credentials(self, project_id: str) -> tuple[str | None, str | None]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT username, token FROM git_credentials WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            if not row:
                return None, None
            return row["username"] or None, row["token"] or None

    def set_git_credentials(
        self,
        project_id: str,
        username: str | None,
        token: str | None,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO git_credentials(project_id, username, token, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                    username = excluded.username,
                    token = excluded.token,
                    updated_at = excluded.updated_at
                """,
                (project_id, username, token, datetime.now().isoformat()),
            )

    def delete_git_credentials(self, project_id: str) -> bool:
        with self._lock, self._connect() as conn:
            result = conn.execute(
                "DELETE FROM git_credentials WHERE project_id = ?",
                (project_id,),
            )
            return result.rowcount > 0
