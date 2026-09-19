#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import re
import shutil


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

new = upsert(old, "features", "memories", "true")
new = upsert(new, "agents", "max_concurrent_threads_per_session", "6")

if new != old:
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, path.with_name(f"config.toml.backup-ge360-{stamp}"))
    path.write_text(new.rstrip() + "\n", encoding="utf-8")
    print(f"[OK] Configurazione Codex aggiornata: {path}")
else:
    print(f"[OK] Configurazione Codex già pronta: {path}")
