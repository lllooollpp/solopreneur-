"""One-time migration from legacy file storage to SQLite-only storage."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from nanobot.storage.sqlite_store import SQLiteStore


def migrate_sessions(data_dir: Path, store: SQLiteStore) -> int:
    sessions_dir = data_dir / "sessions"
    if not sessions_dir.exists():
        return 0

    migrated = 0
    for path in sessions_dir.glob("*.jsonl"):
        key = path.stem.replace("_", ":")
        messages = []
        metadata = {}
        created_at = datetime.now()
        updated_at = datetime.now()
        signature = ""

        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    if item.get("_type") == "metadata":
                        metadata = item.get("metadata", {})
                        if item.get("created_at"):
                            created_at = datetime.fromisoformat(item["created_at"])
                        if item.get("updated_at"):
                            updated_at = datetime.fromisoformat(item["updated_at"])
                        signature = item.get("signature", "")
                    else:
                        messages.append(item)

            if not signature:
                # 给空签名预留占位，后续由 SessionManager 重新生成
                signature = "legacy-migration"

            store.save_session(
                key=key,
                signature=signature,
                metadata=metadata,
                created_at=created_at,
                updated_at=updated_at,
                messages=messages,
            )
            migrated += 1
        except Exception as e:
            print(f"[WARN] skip session {path.name}: {e}")

    return migrated


def migrate_projects(data_dir: Path, store: SQLiteStore) -> int:
    projects_file = data_dir / "projects.json"
    if not projects_file.exists():
        return 0

    try:
        with open(projects_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        print(f"[WARN] cannot read projects.json: {e}")
        return 0

    migrated = 0
    for proj in payload.get("projects", []):
        try:
            store.save_project(proj)
            migrated += 1
        except Exception as e:
            print(f"[WARN] skip project {proj.get('id')}: {e}")
    return migrated


def migrate_git_credentials(data_dir: Path, store: SQLiteStore) -> int:
    cred_file = data_dir / ".git_credentials.json"
    if not cred_file.exists():
        return 0

    try:
        with open(cred_file, "r", encoding="utf-8") as f:
            creds = json.load(f)
    except Exception as e:
        print(f"[WARN] cannot read .git_credentials.json: {e}")
        return 0

    migrated = 0
    for project_id, info in creds.items():
        username = info.get("username") or None
        token = info.get("token") or None
        store.set_git_credentials(project_id, username, token)
        migrated += 1
    return migrated


def migrate_session_secret(data_dir: Path, store: SQLiteStore) -> bool:
    secret_file = data_dir / ".session_secret"
    if not secret_file.exists():
        return False

    secret = secret_file.read_text(encoding="utf-8").strip()
    if not secret:
        return False

    store.set_kv("session_secret", secret)
    return True


def main() -> int:
    data_dir = Path.home() / ".nanobot"
    store = SQLiteStore(data_dir / "nanobot.db")

    print(f"[INFO] migrating legacy files from: {data_dir}")
    session_count = migrate_sessions(data_dir, store)
    project_count = migrate_projects(data_dir, store)
    cred_count = migrate_git_credentials(data_dir, store)
    secret_migrated = migrate_session_secret(data_dir, store)

    print(f"[OK] sessions migrated: {session_count}")
    print(f"[OK] projects migrated: {project_count}")
    print(f"[OK] git credentials migrated: {cred_count}")
    print(f"[OK] session secret migrated: {secret_migrated}")
    print("[DONE] migration finished. You can archive or remove legacy files manually.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
