#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import sqlite3
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
STATE = RUNTIME / "migration-state.json"
DB = RUNTIME / "jarvis-smart.sqlite3"


def load_release() -> dict:
    return json.loads((ROOT / "release.json").read_text(encoding="utf-8"))


def load_state() -> dict:
    if not STATE.exists():
        return {"schema_version": 0, "applied": []}
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": 0, "applied": []}


def save_state(state: dict) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(STATE)


def migration_1() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                status TEXT NOT NULL,
                event_type TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT 'ge360'
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_activity_session ON agent_activity(session, id DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_activity_agent ON agent_activity(agent_id, id DESC)"
        )
        conn.commit()
    finally:
        conn.close()


def migration_2() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id TEXT PRIMARY KEY,
                uploaded_at TEXT NOT NULL,
                original_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_uploaded_files_uploaded_at ON uploaded_files(uploaded_at DESC)"
        )
        conn.commit()
    finally:
        conn.close()


def migration_3() -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_threads (
                thread_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                cwd TEXT NOT NULL,
                model TEXT NOT NULL,
                effort TEXT NOT NULL,
                primary_agent TEXT NOT NULL,
                collaborators_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'idle',
                current_turn_id TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                role TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'message',
                item_id TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'completed',
                meta_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_server_requests (
                request_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                method TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                result_json TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                resolved_at TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_threads_updated ON chat_threads(updated_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_thread ON chat_messages(thread_id, id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_item ON chat_messages(thread_id, item_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_requests_thread ON chat_server_requests(thread_id, created_at)"
        )
        conn.commit()
    finally:
        conn.close()


MIGRATIONS = {
    1: migration_1,
    2: migration_2,
    3: migration_3,
}


def main() -> int:
    release = load_release()
    target = int(release.get("schema_version", 0))
    state = load_state()
    current = int(state.get("schema_version", 0))

    if current > target:
        print(f"[FAIL] Schema runtime {current} più nuovo del software {target}.")
        return 2

    for version in range(current + 1, target + 1):
        fn = MIGRATIONS.get(version)
        if fn is None:
            print(f"[FAIL] Migrazione {version} mancante.")
            return 3
        print(f"[MIGRATE] {current} -> {version}")
        fn()
        state["schema_version"] = version
        state.setdefault("applied", []).append({
            "version": version,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        save_state(state)
        current = version

    print(f"[OK] Runtime schema {current} / release {release.get('version')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
