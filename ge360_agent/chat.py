from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "runtime" / "jarvis-smart.sqlite3"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def create_thread(
    thread_id: str,
    title: str,
    workspace_id: str,
    cwd: str,
    model: str,
    effort: str,
    primary_agent: str,
    collaborators: list[str],
) -> dict:
    ts = now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO chat_threads
            (thread_id, title, workspace_id, cwd, model, effort, primary_agent,
             collaborators_json, status, current_turn_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'idle', '', ?, ?)
            """,
            (
                thread_id,
                title[:160],
                workspace_id,
                cwd,
                model,
                effort,
                primary_agent,
                json.dumps(collaborators, ensure_ascii=False),
                ts,
                ts,
            ),
        )
        conn.commit()
    return get_thread(thread_id) or {}


def get_thread(thread_id: str) -> dict | None:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT * FROM chat_threads WHERE thread_id=?",
                (thread_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
    if not row:
        return None
    item = dict(row)
    try:
        item["collaborators"] = json.loads(item.pop("collaborators_json") or "[]")
    except Exception:
        item["collaborators"] = []
    return item


def list_threads(limit: int = 40) -> list[dict]:
    with _connect() as conn:
        try:
            rows = conn.execute(
                """
                SELECT * FROM chat_threads
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (max(1, min(limit, 200)),),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["collaborators"] = json.loads(item.pop("collaborators_json") or "[]")
        except Exception:
            item["collaborators"] = []
        result.append(item)
    return result


def update_thread(
    thread_id: str,
    *,
    status: str | None = None,
    turn_id: str | None = None,
    title: str | None = None,
) -> None:
    fields = ["updated_at=?"]
    values: list[object] = [now()]
    if status is not None:
        fields.append("status=?")
        values.append(status)
    if turn_id is not None:
        fields.append("current_turn_id=?")
        values.append(turn_id)
    if title is not None:
        fields.append("title=?")
        values.append(title[:160])
    values.append(thread_id)
    with _connect() as conn:
        conn.execute(
            f"UPDATE chat_threads SET {', '.join(fields)} WHERE thread_id=?",
            values,
        )
        conn.commit()


def add_message(
    thread_id: str,
    role: str,
    content: str,
    *,
    kind: str = "message",
    item_id: str = "",
    status: str = "completed",
    meta: dict | None = None,
) -> dict:
    ts = now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO chat_messages
            (thread_id, role, kind, item_id, content, status, meta_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                thread_id,
                role,
                kind,
                item_id,
                content,
                status,
                json.dumps(meta or {}, ensure_ascii=False),
                ts,
                ts,
            ),
        )
        conn.execute(
            "UPDATE chat_threads SET updated_at=? WHERE thread_id=?",
            (ts, thread_id),
        )
        conn.commit()
        row_id = int(cur.lastrowid)
    return get_message(row_id) or {}


def get_message(message_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM chat_messages WHERE id=?",
            (message_id,),
        ).fetchone()
    return _message_dict(row) if row else None


def _message_dict(row) -> dict:
    item = dict(row)
    try:
        item["meta"] = json.loads(item.pop("meta_json") or "{}")
    except Exception:
        item["meta"] = {}
    return item


def list_messages(thread_id: str, limit: int = 300) -> list[dict]:
    limit = max(1, min(limit, 1000))
    with _connect() as conn:
        try:
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM chat_messages
                    WHERE thread_id=?
                    ORDER BY id DESC LIMIT ?
                )
                ORDER BY id ASC
                """,
                (thread_id, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    return [_message_dict(row) for row in rows]


def find_by_item(thread_id: str, item_id: str) -> dict | None:
    if not item_id:
        return None
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM chat_messages
            WHERE thread_id=? AND item_id=?
            ORDER BY id DESC LIMIT 1
            """,
            (thread_id, item_id),
        ).fetchone()
    return _message_dict(row) if row else None


def append_delta(
    thread_id: str,
    item_id: str,
    delta: str,
    *,
    role: str = "assistant",
    kind: str = "message",
) -> dict:
    if not delta:
        return find_by_item(thread_id, item_id) or {}
    existing = find_by_item(thread_id, item_id)
    ts = now()
    if existing:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE chat_messages
                SET content=content || ?, status='in_progress', updated_at=?
                WHERE id=?
                """,
                (delta, ts, existing["id"]),
            )
            conn.execute(
                "UPDATE chat_threads SET updated_at=? WHERE thread_id=?",
                (ts, thread_id),
            )
            conn.commit()
        return get_message(int(existing["id"])) or {}
    return add_message(
        thread_id,
        role,
        delta,
        kind=kind,
        item_id=item_id,
        status="in_progress",
    )


def upsert_item(
    thread_id: str,
    item_id: str,
    *,
    role: str,
    kind: str,
    content: str,
    status: str,
    meta: dict | None = None,
) -> dict:
    existing = find_by_item(thread_id, item_id)
    if not existing:
        return add_message(
            thread_id,
            role,
            content,
            kind=kind,
            item_id=item_id,
            status=status,
            meta=meta,
        )
    with _connect() as conn:
        conn.execute(
            """
            UPDATE chat_messages
            SET role=?, kind=?, content=?, status=?, meta_json=?, updated_at=?
            WHERE id=?
            """,
            (
                role,
                kind,
                content,
                status,
                json.dumps(meta or existing.get("meta", {}), ensure_ascii=False),
                now(),
                existing["id"],
            ),
        )
        conn.commit()
    return get_message(int(existing["id"])) or {}


def update_item_status(thread_id: str, item_id: str, status: str, *, meta: dict | None = None) -> dict:
    existing = find_by_item(thread_id, item_id)
    if not existing:
        return {}
    with _connect() as conn:
        if meta is None:
            conn.execute(
                "UPDATE chat_messages SET status=?, updated_at=? WHERE id=?",
                (status, now(), existing["id"]),
            )
        else:
            conn.execute(
                """
                UPDATE chat_messages
                SET status=?, meta_json=?, updated_at=?
                WHERE id=?
                """,
                (status, json.dumps(meta, ensure_ascii=False), now(), existing["id"]),
            )
        conn.commit()
    return get_message(int(existing["id"])) or {}


def create_server_request(
    request_id: str,
    thread_id: str,
    method: str,
    params: dict,
) -> dict:
    ts = now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO chat_server_requests
            (request_id, thread_id, method, payload_json, status, result_json, created_at, resolved_at)
            VALUES (?, ?, ?, ?, 'pending', '', ?, '')
            """,
            (
                request_id,
                thread_id,
                method,
                json.dumps(params, ensure_ascii=False),
                ts,
            ),
        )
        conn.commit()
    return get_server_request(request_id) or {}


def get_server_request(request_id: str) -> dict | None:
    with _connect() as conn:
        try:
            row = conn.execute(
                "SELECT * FROM chat_server_requests WHERE request_id=?",
                (request_id,),
            ).fetchone()
        except sqlite3.OperationalError:
            return None
    if not row:
        return None
    item = dict(row)
    try:
        item["payload"] = json.loads(item.pop("payload_json") or "{}")
    except Exception:
        item["payload"] = {}
    try:
        item["result"] = json.loads(item.pop("result_json") or "{}") if item["result_json"] else {}
    except Exception:
        item["result"] = {}
        item.pop("result_json", None)
    return item


def resolve_server_request(request_id: str, result: dict) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE chat_server_requests
            SET status='resolved', result_json=?, resolved_at=?
            WHERE request_id=?
            """,
            (json.dumps(result, ensure_ascii=False), now(), request_id),
        )
        conn.commit()
