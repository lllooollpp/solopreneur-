"""SQLite read-only inspection tool for persistence diagnostics."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from nanobot.agent.core.tools.base import Tool


class DBInspectTool(Tool):
    """Read-only database inspect tool for nanobot SQLite."""

    def __init__(self, db_path: Path | None = None, default_limit: int = 100):
        self.db_path = db_path or (Path.home() / ".nanobot" / "nanobot.db")
        self.default_limit = max(1, min(default_limit, 500))

    @property
    def name(self) -> str:
        return "db_inspect"

    @property
    def description(self) -> str:
        return (
            "Inspect nanobot SQLite in read-only mode. "
            "Actions: list_tables, schema, count, sample, query(select only)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_tables", "schema", "count", "sample", "query"],
                    "description": "Inspection action",
                },
                "table": {
                    "type": "string",
                    "description": "Table name (required for schema/count/sample)",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 500,
                    "description": "Max rows for sample/query",
                    "default": 50,
                },
                "sql": {
                    "type": "string",
                    "description": "SELECT SQL text (required for action=query)",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        table: str | None = None,
        limit: int | None = None,
        sql: str | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.db_path.exists():
            return f"Error: database not found: {self.db_path}"

        row_limit = max(1, min(limit or self.default_limit, 500))

        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row

                if action == "list_tables":
                    rows = conn.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type='table' AND name NOT LIKE 'sqlite_%'
                        ORDER BY name
                        """
                    ).fetchall()
                    return "\n".join([r["name"] for r in rows]) or "(no tables)"

                if action in {"schema", "count", "sample"} and not table:
                    return "Error: 'table' is required for this action"

                if action == "schema":
                    rows = conn.execute(f"PRAGMA table_info({self._safe_ident(table)})").fetchall()
                    if not rows:
                        return f"Error: table not found: {table}"
                    lines = [f"Schema for {table}:"]
                    for r in rows:
                        line = (
                            f"- {r['name']} {r['type']}"
                            f"{' NOT NULL' if r['notnull'] else ''}"
                            f"{' PK' if r['pk'] else ''}"
                        )
                        if r["dflt_value"] is not None:
                            line += f" DEFAULT {r['dflt_value']}"
                        lines.append(line)
                    return "\n".join(lines)

                if action == "count":
                    value = conn.execute(
                        f"SELECT COUNT(*) AS n FROM {self._safe_ident(table)}"
                    ).fetchone()["n"]
                    return f"{table}: {value}"

                if action == "sample":
                    rows = conn.execute(
                        f"SELECT * FROM {self._safe_ident(table)} LIMIT ?",
                        (row_limit,),
                    ).fetchall()
                    return self._rows_to_text(rows)

                if action == "query":
                    if not sql:
                        return "Error: 'sql' is required for action=query"
                    guard = self._guard_sql(sql)
                    if guard:
                        return guard

                    sql_text = sql.strip().rstrip(";")
                    if " limit " not in sql_text.lower():
                        sql_text = f"{sql_text} LIMIT {row_limit}"

                    rows = conn.execute(sql_text).fetchall()
                    return self._rows_to_text(rows)

                return f"Error: unsupported action: {action}"
        except sqlite3.Error as e:
            return f"Error: sqlite failed: {e}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _safe_ident(name: str | None) -> str:
        if not name:
            raise ValueError("missing table name")
        if not all(c.isalnum() or c == "_" for c in name):
            raise ValueError(f"invalid identifier: {name}")
        return name

    @staticmethod
    def _guard_sql(sql: str) -> str | None:
        text = sql.strip().lower()
        banned = ["insert", "update", "delete", "drop", "alter", "create", "replace", "pragma", "attach"]
        if not text.startswith("select"):
            return "Error: only SELECT queries are allowed"
        if any(f" {kw} " in f" {text} " for kw in banned):
            return "Error: non-read-only SQL detected"
        return None

    @staticmethod
    def _rows_to_text(rows: list[sqlite3.Row]) -> str:
        if not rows:
            return "(no rows)"
        lines: list[str] = []
        for i, r in enumerate(rows, start=1):
            data = {k: r[k] for k in r.keys()}
            lines.append(f"[{i}] {data}")
        return "\n".join(lines)
