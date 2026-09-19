#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import re
import shutil
import tomllib


def upsert_root(text: str, key: str, value: str) -> str:
    key_re = re.compile(rf"(?m)^\s*{re.escape(key)}\s*=.*$")
    if key_re.search(text):
        return key_re.sub(f"{key} = {value}", text, count=1)

    first_header = re.search(r"(?m)^\s*\[[^\]]+\]\s*(?:#.*)?$", text)
    line = f"{key} = {value}\n"
    if first_header:
        prefix = text[:first_header.start()].rstrip()
        suffix = text[first_header.start():].lstrip()
        return (prefix + "\n" if prefix else "") + line + "\n" + suffix
    return text.rstrip() + ("\n" if text.strip() else "") + line


def upsert(text: str, section: str, key: str, value: str) -> str:
    header = re.compile(rf"(?m)^\s*\[{re.escape(section)}\]\s*(?:#.*)?$")
    match = header.search(text)
    key_re = re.compile(rf"(?m)^\s*{re.escape(key)}\s*=.*$")

    if match:
        next_header = re.search(r"(?m)^\s*\[[^\]]+\]\s*(?:#.*)?$", text[match.end():])
        end = match.end() + (next_header.start() if next_header else len(text) - match.end())
        body = text[match.end():end]
        if key_re.search(body):
            body = key_re.sub(f"{key} = {value}", body, count=1)
        else:
            body = body.rstrip() + f"\n{key} = {value}\n"
        return text[:match.end()] + body + text[end:]

    return text.rstrip() + ("\n\n" if text.strip() else "") + f"[{section}]\n{key} = {value}\n"


codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
codex_home.mkdir(parents=True, exist_ok=True)
path = codex_home / "config.toml"
old = path.read_text(encoding="utf-8") if path.exists() else ""

parsed = {}
if old.strip():
    try:
        parsed = tomllib.loads(old)
    except tomllib.TOMLDecodeError as exc:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        broken = path.with_name(f"config.toml.corrotto-ge360-{stamp}")
        shutil.copy2(path, broken)
        print(f"[WARN] config.toml non valido: {exc}")
        print(f"[OK] Copia del file corrotto salvata in: {broken}")

        candidates = sorted(
            list(codex_home.glob("config.toml.backup-ge360-*")) +
            ([codex_home / "config.toml.save"] if (codex_home / "config.toml.save").exists() else []),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        recovered = ""
        recovered_from = None
        for candidate in candidates:
            try:
                candidate_text = candidate.read_text(encoding="utf-8")
                tomllib.loads(candidate_text)
                recovered = candidate_text
                recovered_from = candidate
                break
            except Exception:
                continue

        if recovered_from:
            old = recovered
            print(f"[OK] Ripristino automatico da backup valido: {recovered_from}")
        else:
            old = ""
            print("[WARN] Nessun backup TOML valido trovato: ricreo una configurazione Codex minima.")
            
if (
    parsed.get("cli_auth_credentials_store") == "file"
    and parsed.get("features", {}).get("memories") is True
    and parsed.get("agents", {}).get("max_concurrent_threads_per_session") == 6
):
    print(f"[OK] Configurazione Codex già pronta: {path}")
    raise SystemExit(0)

new = upsert_root(old, "cli_auth_credentials_store", '"file"')
new = upsert(new, "features", "memories", "true")
new = upsert(new, "agents", "max_concurrent_threads_per_session", "6")

try:
    tomllib.loads(new)
except tomllib.TOMLDecodeError as exc:
    raise SystemExit(f"[FAIL] La modifica produrrebbe TOML non valido: {exc}")

if new != old:
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, path.with_name(f"config.toml.backup-ge360-{stamp}"))
    path.write_text(new.rstrip() + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    print(f"[OK] Configurazione Codex aggiornata: {path}")
else:
    print(f"[OK] Configurazione Codex già pronta: {path}")
