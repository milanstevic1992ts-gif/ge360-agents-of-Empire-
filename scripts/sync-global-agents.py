#!/usr/bin/env python3
from pathlib import Path
import sys

MARKER = "GE360-JARVIS-GLOBAL-POLICY"
BEGIN = f"<!-- {MARKER} BEGIN -->"
END = f"<!-- {MARKER} END -->"

if len(sys.argv) != 3:
    raise SystemExit("uso: sync-global-agents.py SOURCE TARGET")

source = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
target = Path(sys.argv[2])
old = target.read_text(encoding="utf-8") if target.exists() else ""
block = f"{BEGIN}\n{source}\n{END}"

if BEGIN in old and END in old:
    before, rest = old.split(BEGIN, 1)
    _, after = rest.split(END, 1)
    new = before.rstrip() + "\n\n" + block + after
else:
    new = old.rstrip() + ("\n\n" if old.strip() else "") + block + "\n"

target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(new.rstrip() + "\n", encoding="utf-8")
