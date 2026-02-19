"""
Trace events API — 查询、审计协作调用链与原始事件流
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from loguru import logger

from solopreneur.storage.services import TracePersistence

router = APIRouter()

_trace_svc: TracePersistence | None = None


def _get_trace_svc() -> TracePersistence:
    global _trace_svc
    if _trace_svc is None:
        _trace_svc = TracePersistence()
    return _trace_svc


@router.get("/traces/{session_key}")
async def list_trace_requests(session_key: str):
    """列出某个 session 下的所有请求（按时间倒序），用于历史列表。"""
    svc = _get_trace_svc()
    requests = svc.list_requests(session_key)
    return {"session_key": session_key, "requests": requests}


@router.get("/traces/{session_key}/events")
async def get_trace_events(
    session_key: str,
    request_id: str | None = Query(None, description="过滤到具体的 request_id"),
    limit: int = Query(500, ge=1, le=5000, description="最大返回事件数"),
):
    """获取某个 session（或某次请求）的全部 trace 事件，用于审计和回放。"""
    svc = _get_trace_svc()
    events = svc.load(session_key=session_key, request_id=request_id, limit=limit)
    return {"session_key": session_key, "request_id": request_id, "events": events}


@router.delete("/traces/{session_key}")
async def delete_trace_events(
    session_key: str,
    request_id: str | None = Query(None),
):
    """删除 trace 事件（整个 session 或单次请求）。"""
    svc = _get_trace_svc()
    deleted = svc.delete(session_key, request_id)
    logger.info(f"Deleted {deleted} trace events for session={session_key} request={request_id}")
    return {"deleted": deleted}
