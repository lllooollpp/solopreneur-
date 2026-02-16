"""
指标查询 API 端点
提供 llm_usage 与 subagent_tasks 的聚合统计
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter()


def _db_path() -> Path:
    return Path.home() / ".nanobot" / "nanobot.db"


class UsageSummary(BaseModel):
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    avg_duration_ms: int = 0
    stream_calls: int = 0


class TaskSummary(BaseModel):
    total: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)


class MetricsSnapshot(BaseModel):
    usage: UsageSummary
    tasks: TaskSummary


@router.get("/metrics/usage/summary", response_model=UsageSummary)
async def usage_summary(
    days: int = Query(7, ge=1, le=365),
    session_key: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
):
    try:
        db = _db_path()
        if not db.exists():
            raise HTTPException(status_code=404, detail=f"Database not found: {db}")

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

        with sqlite3.connect(str(db)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(sql, tuple(params)).fetchone()

        return UsageSummary(
            calls=int(row["calls"] or 0),
            prompt_tokens=int(row["prompt_tokens"] or 0),
            completion_tokens=int(row["completion_tokens"] or 0),
            total_tokens=int(row["total_tokens"] or 0),
            avg_duration_ms=int(row["avg_duration_ms"] or 0),
            stream_calls=int(row["stream_calls"] or 0),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/usage/daily")
async def usage_daily(
    days: int = Query(7, ge=1, le=365),
    session_key: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
):
    try:
        db = _db_path()
        if not db.exists():
            raise HTTPException(status_code=404, detail=f"Database not found: {db}")

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

        with sqlite3.connect(str(db)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, tuple(params)).fetchall()

        return {
            "days": days,
            "rows": [
                {
                    "day": r["day"],
                    "calls": int(r["calls"] or 0),
                    "prompt_tokens": int(r["prompt_tokens"] or 0),
                    "completion_tokens": int(r["completion_tokens"] or 0),
                    "total_tokens": int(r["total_tokens"] or 0),
                    "avg_duration_ms": int(r["avg_duration_ms"] or 0),
                }
                for r in rows
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/tasks/summary", response_model=TaskSummary)
async def task_summary(
    days: int = Query(7, ge=1, le=365),
    status: Optional[str] = Query(None),
):
    try:
        db = _db_path()
        if not db.exists():
            raise HTTPException(status_code=404, detail=f"Database not found: {db}")

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

        with sqlite3.connect(str(db)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, tuple(params)).fetchall()

        by_status = {r["status"]: int(r["cnt"] or 0) for r in rows}
        return TaskSummary(total=sum(by_status.values()), by_status=by_status)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/tasks/daily")
async def task_daily(
    days: int = Query(7, ge=1, le=365),
    status: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
):
    try:
        db = _db_path()
        if not db.exists():
            raise HTTPException(status_code=404, detail=f"Database not found: {db}")

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

        with sqlite3.connect(str(db)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, tuple(params)).fetchall()

        return {
            "days": days,
            "rows": [
                {
                    "day": r["day"],
                    "status": r["status"],
                    "count": int(r["cnt"] or 0),
                }
                for r in rows
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/snapshot", response_model=MetricsSnapshot)
async def metrics_snapshot(
    days: int = Query(7, ge=1, le=365),
    session_key: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
):
    usage = await usage_summary(days=days, session_key=session_key, model=model)
    tasks = await task_summary(days=days, status=None)
    return MetricsSnapshot(usage=usage, tasks=tasks)
