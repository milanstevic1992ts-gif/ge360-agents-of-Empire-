from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "runtime" / "jarvis-smart.sqlite3"

VALID_STATUSES = {"idle", "working", "waiting", "error", "done", "ready"}


def record(
    session: str,
    agent_id: str,
    status: str,
    event_type: str,
    detail: str = "",
    source: str = "ge360",
) -> None:
    if status not in VALID_STATUSES:
        status = "ready"
    DB.parent.mkdir(parents=True, exist_ok=True)
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
            """
            INSERT INTO agent_activity
            (created_at, session, agent_id, status, event_type, detail, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                session,
                agent_id,
                status,
                event_type,
                detail[:1000],
                source,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def latest_by_agent(limit: int = 100) -> dict[str, dict]:
    if not DB.exists():
        return {}
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT a.*
            FROM agent_activity a
            JOIN (
                SELECT agent_id, MAX(id) AS max_id
                FROM agent_activity
                GROUP BY agent_id
            ) latest ON latest.max_id = a.id
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (max(1, min(limit, 500)),),
        ).fetchall()
        return {str(r["agent_id"]): dict(r) for r in rows}
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()


def timeline(limit: int = 80, session: str = "") -> list[dict]:
    if not DB.exists():
        return []
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    try:
        if session:
            rows = conn.execute(
                """
                SELECT * FROM agent_activity
                WHERE session=?
                ORDER BY id DESC LIMIT ?
                """,
                (session, max(1, min(limit, 500))),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_activity ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def agents_for_session(session: str) -> list[str]:
    if not DB.exists():
        return []
    conn = sqlite3.connect(DB)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT agent_id
            FROM agent_activity
            WHERE session=?
            ORDER BY agent_id
            """,
            (session,),
        ).fetchall()
        return [str(row[0]) for row in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
