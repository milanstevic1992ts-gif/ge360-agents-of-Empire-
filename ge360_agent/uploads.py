from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import os
import re
import sqlite3
import uuid


ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "runtime" / "jarvis-smart.sqlite3"
INBOX = Path(
    os.environ.get(
        "GE360_JARVIS_INBOX",
        str(Path.home() / ".local" / "share" / "ge360-jarvis" / "inbox"),
    )
).expanduser()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".json", ".txt"}
MAX_FILE_BYTES = 25 * 1024 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._ -]+")


def safe_filename(name: str) -> str:
    base = Path(name or "upload").name.strip()
    base = _SAFE_NAME.sub("_", base)
    base = re.sub(r"\s+", " ", base).strip(" .")
    return (base or "upload")[:180]


def extension_allowed(name: str) -> bool:
    return Path(name).suffix.lower() in ALLOWED_EXTENSIONS


def _connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def register_file(
    file_id: str,
    original_name: str,
    stored_path: Path,
    size_bytes: int,
    sha256: str,
    content_type: str,
) -> dict:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO uploaded_files
            (id, uploaded_at, original_name, stored_path, size_bytes, sha256, content_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                datetime.now(timezone.utc).isoformat(),
                original_name,
                str(stored_path),
                size_bytes,
                sha256,
                content_type,
            ),
        )
        conn.commit()
    return get_file(file_id)


def get_file(file_id: str) -> dict:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, uploaded_at, original_name, stored_path,
                   size_bytes, sha256, content_type
            FROM uploaded_files WHERE id=?
            """,
            (file_id,),
        ).fetchone()
    if not row:
        raise KeyError(file_id)
    item = dict(row)
    item["exists"] = Path(item["stored_path"]).is_file()
    return item


def list_files(limit: int = 100) -> list[dict]:
    with _connect() as conn:
        try:
            rows = conn.execute(
                """
                SELECT id, uploaded_at, original_name, stored_path,
                       size_bytes, sha256, content_type
                FROM uploaded_files
                ORDER BY uploaded_at DESC LIMIT ?
                """,
                (max(1, min(limit, 500)),),
            ).fetchall()
        except sqlite3.OperationalError:
            return []
    result = []
    for row in rows:
        item = dict(row)
        item["exists"] = Path(item["stored_path"]).is_file()
        result.append(item)
    return result


def resolve_files(ids: list[str]) -> list[dict]:
    result = []
    for file_id in ids[:20]:
        try:
            item = get_file(file_id)
        except KeyError:
            continue
        if item["exists"]:
            result.append(item)
    return result


async def save_upload(upload) -> dict:
    original = safe_filename(upload.filename or "upload")
    if not extension_allowed(original):
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Formato non supportato. Usa: {allowed}")

    file_id = uuid.uuid4().hex[:16]
    folder = INBOX / file_id
    folder.mkdir(parents=True, exist_ok=False)
    target = folder / original
    tmp = folder / (original + ".part")

    hasher = hashlib.sha256()
    size = 0
    try:
        with tmp.open("wb") as fh:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    raise ValueError("File troppo grande: limite 25 MB")
                hasher.update(chunk)
                fh.write(chunk)
        tmp.replace(target)
        return register_file(
            file_id=file_id,
            original_name=original,
            stored_path=target,
            size_bytes=size,
            sha256=hasher.hexdigest(),
            content_type=(upload.content_type or "application/octet-stream")[:120],
        )
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            folder.rmdir()
        except OSError:
            pass
        raise


def attachment_context(files: list[dict]) -> str:
    if not files:
        return ""
    lines = ["ALLEGATI DISPONIBILI SUL SERVER:"]
    for item in files:
        lines.append(
            f"- {item['original_name']} | path: {item['stored_path']} | "
            f"{item['size_bytes']} bytes | sha256: {item['sha256']}"
        )
    lines.append(
        "Lavora su questi percorsi reali. Non modificare i file originali; "
        "crea sempre output derivati separati."
    )
    return "\n".join(lines)
