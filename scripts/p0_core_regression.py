"""P0 核心回归检查脚本（聚焦持久化主链路）�?""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from solopreneur.projects.manager import ProjectManager
from solopreneur.session.manager import SessionManager
from solopreneur.storage.sqlite_store import SQLiteStore


def check_session_flow() -> tuple[bool, str]:
    sm = SessionManager(Path("."))
    key = "cli:p0-regression"
    session = sm.get_or_create(key)
    session.clear()
    session.add_message("user", "hello")
    session.add_message("assistant", "world")
    sm.save(session)

    loaded = sm.get_or_create(key)
    ok = len(loaded.messages) >= 2 and loaded.messages[-1].get("content") == "world"
    return ok, f"session messages={len(loaded.messages)}"


def check_project_flow() -> tuple[bool, str]:
    pm = ProjectManager()
    projects = pm.list_projects()
    return len(projects) > 0, f"projects count={len(projects)}"


def check_usage_and_task_flow() -> tuple[bool, str]:
    store = SQLiteStore()
    store.record_llm_usage(
        session_key="cli:p0-regression",
        model="p0-model",
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        duration_ms=150,
        is_stream=False,
    )
    store.upsert_subagent_task(
        task_id="p0-regression-task",
        label="P0 Regression",
        task_text="validate task persistence",
        origin_channel="cli",
        origin_chat_id="direct",
        status="pending",
    )
    store.upsert_subagent_task(
        task_id="p0-regression-task",
        label="P0 Regression",
        task_text="validate task persistence",
        origin_channel="cli",
        origin_chat_id="direct",
        status="success",
        result_text="ok",
    )

    db = Path.home() / ".nanobot" / "nanobot.db"
    conn = sqlite3.connect(str(db))
    c = conn.cursor()
    c.execute(
        "select count(1) from llm_usage where session_key=? and model=?",
        ("cli:p0-regression", "p0-model"),
    )
    usage_rows = c.fetchone()[0]

    c.execute(
        "select status from subagent_tasks where task_id=?",
        ("p0-regression-task",),
    )
    task_status = c.fetchone()[0]

    conn.close()
    ok = usage_rows > 0 and task_status == "success"
    return ok, f"usage_rows={usage_rows}, task_status={task_status}"


def main() -> int:
    checks = [
        ("session_flow", check_session_flow),
        ("project_flow", check_project_flow),
        ("usage_task_flow", check_usage_and_task_flow),
    ]

    failed = []
    print(f"[P0] Core regression start: {datetime.now().isoformat()}")
    for name, fn in checks:
        try:
            ok, detail = fn()
            status = "PASS" if ok else "FAIL"
            print(f"- {name}: {status} | {detail}")
            if not ok:
                failed.append(name)
        except Exception as e:
            print(f"- {name}: FAIL | exception={type(e).__name__}: {e}")
            failed.append(name)

    if failed:
        print(f"[P0] Core regression failed: {failed}")
        return 1

    print("[P0] Core regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
