"""Metrics inspection tool for SQLite persistence dashboards."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from nanobot.agent.core.tools.base import Tool


class MetricsInspectTool(Tool):
    """Aggregate llm_usage/subagent_tasks metrics for quick diagnostics."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or (Path.home() / ".nanobot" / "nanobot.db")

    @property
    def name(self) -> str:
        return "metrics_inspect"

    @property
    def description(self) -> str:
        return (
            "Inspect aggregated metrics from SQLite. "
            "Actions: usage_daily, usage_summary, task_daily, task_summary, snapshot."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "usage_daily",
                        "usage_summary",
                        "task_daily",
                        "task_summary",
                        "snapshot",
                    ],
                    "description": "Metric action",
                },
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 365,
                    "default": 7,
                    "description": "Lookback window in days",
                },
                "session_key": {
                    "type": "string",
                    "description": "Optional session key filter for usage",
                },
                "model": {
                    "type": "string",
                    "description": "Optional model filter for usage",
                },
                "status": {
                    "type": "string",
                    "description": "Optional task status filter",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                    "description": "Max returned rows for grouped output",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        days: int = 7,
        session_key: str | None = None,
        model: str | None = None,
        status: str | None = None,
        limit: int = 20,
        **kwargs: Any,
    ) -> str:
        if not self.db_path.exists():
            return f"Error: database not found: {self.db_path}"

        days = max(1, min(days, 365))
        limit = max(1, min(limit, 100))

        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                if action == "usage_daily":
                    return self._usage_daily(conn, days, session_key, model, limit)
                if action == "usage_summary":
                    return self._usage_summary(conn, days, session_key, model)
                if action == "task_daily":
                    return self._task_daily(conn, days, status, limit)
                if action == "task_summary":
                    return self._task_summary(conn, days, status)
                if action == "snapshot":
                    usage = self._usage_summary(conn, days, session_key, model)
                    tasks = self._task_summary(conn, days, status)
                    return f"# usage\n{usage}\n\n# tasks\n{tasks}"

                return f"Error: unsupported action: {action}"
        except sqlite3.Error as e:
            return f"Error: sqlite failed: {e}"
        except Exception as e:
            return f"Error: {e}"

    def _usage_daily(
        self,
        conn: sqlite3.Connection,
        days: int,
        session_key: str | None,
        model: str | None,
        limit: int,
    ) -> str:
        sql = (
            """
            SELECT substr(created_at, 1, 10) AS day,
                   COUNT(*) AS calls,
                   SUM(prompt_tokens) AS prompt_tokens,
                   SUM(completion_tokens) AS completion_tokens,
                   SUM(total_tokens) AS total_tokens,
                   AVG(duration_ms) AS avg_duration_ms
            FROM llm_usage
            WHERE datetime(created_at) >= datetime('now', ?)
            """
        )
        params: list[Any] = [f"-{days} days"]
        if session_key:
            sql += " AND session_key = ?"
            params.append(session_key)
        if model:
            sql += " AND model = ?"
            params.append(model)
        sql += " GROUP BY day ORDER BY day DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, tuple(params)).fetchall()
        if not rows:
            return "(no usage rows)"

        lines = ["day | calls | prompt | completion | total | avg_ms"]
        lines.append("--- | ---: | ---: | ---: | ---: | ---:")
        for r in rows:
            lines.append(
                f"{r['day']} | {r['calls']} | {r['prompt_tokens'] or 0} | "
                f"{r['completion_tokens'] or 0} | {r['total_tokens'] or 0} | {int(r['avg_duration_ms'] or 0)}"
            )
        return "\n".join(lines)

    def _usage_summary(
        self,
        conn: sqlite3.Connection,
        days: int,
        session_key: str | None,
        model: str | None,
    ) -> str:
        sql = (
            """
            SELECT COUNT(*) AS calls,
                   SUM(prompt_tokens) AS prompt_tokens,
                   SUM(completion_tokens) AS completion_tokens,
                   SUM(total_tokens) AS total_tokens,
                   AVG(duration_ms) AS avg_duration_ms,
                   SUM(CASE WHEN is_stream = 1 THEN 1 ELSE 0 END) AS stream_calls
            FROM llm_usage
            WHERE datetime(created_at) >= datetime('now', ?)
            """
        )
        params: list[Any] = [f"-{days} days"]
        if session_key:
            sql += " AND session_key = ?"
            params.append(session_key)
        if model:
            sql += " AND model = ?"
            params.append(model)

        r = conn.execute(sql, tuple(params)).fetchone()
        calls = r["calls"] or 0
        return (
            f"calls={calls}, prompt_tokens={r['prompt_tokens'] or 0}, "
            f"completion_tokens={r['completion_tokens'] or 0}, total_tokens={r['total_tokens'] or 0}, "
            f"avg_duration_ms={int(r['avg_duration_ms'] or 0)}, stream_calls={r['stream_calls'] or 0}"
        )

    def _task_daily(
        self,
        conn: sqlite3.Connection,
        days: int,
        status: str | None,
        limit: int,
    ) -> str:
        sql = (
            """
            SELECT substr(updated_at, 1, 10) AS day,
                   status,
                   COUNT(*) AS cnt
            FROM subagent_tasks
            WHERE datetime(updated_at) >= datetime('now', ?)
            """
        )
        params: list[Any] = [f"-{days} days"]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " GROUP BY day, status ORDER BY day DESC, cnt DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, tuple(params)).fetchall()
        if not rows:
            return "(no task rows)"

        lines = ["day | status | count", "--- | --- | ---:"]
        for r in rows:
            lines.append(f"{r['day']} | {r['status']} | {r['cnt']}")
        return "\n".join(lines)

    def _task_summary(self, conn: sqlite3.Connection, days: int, status: str | None) -> str:
        sql = (
            """
            SELECT status, COUNT(*) AS cnt
            FROM subagent_tasks
            WHERE datetime(updated_at) >= datetime('now', ?)
            """
        )
        params: list[Any] = [f"-{days} days"]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " GROUP BY status ORDER BY cnt DESC"

        rows = conn.execute(sql, tuple(params)).fetchall()
        if not rows:
            return "(no task rows)"

        total = sum(r["cnt"] for r in rows)
        pairs = ", ".join([f"{r['status']}={r['cnt']}" for r in rows])
        return f"total={total}; {pairs}"
