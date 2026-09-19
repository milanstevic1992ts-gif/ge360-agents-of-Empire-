#!/usr/bin/env python3
from pathlib import Path
import json, re, sys, tomllib

RX = re.compile(r"^[a-z][a-z0-9_-]{1,39}$")
root = Path.home() / ".codex" / "agents"
root.mkdir(parents=True, exist_ok=True)

cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

if cmd == "list":
    print("SUBAGENTI CODEX DISPONIBILI")
    print("=" * 60)
    for p in sorted(root.glob("*.toml")):
        try:
            with p.open("rb") as f:
                d = tomllib.load(f)
            print(f"- {d.get('name', p.stem)}: {d.get('description', '')}")
        except Exception as exc:
            print(f"- {p.name}: configurazione non valida ({exc})")
elif cmd == "add":
    if len(sys.argv) < 3:
        raise SystemExit('Uso: jarvis add-agent ID "descrizione"')
    aid = sys.argv[2].strip().lower()
    desc = " ".join(sys.argv[3:]).strip() or f"Specialista GE360 per {aid}."
    if not RX.fullmatch(aid):
        raise SystemExit("ID non valido: usa minuscole, numeri, - o _.")
    p = root / f"{aid}.toml"
    if p.exists():
        raise SystemExit(f"Esiste già: {p}")
    instructions = (
        f"You are the GE360 specialist named {aid}. Your domain is: {desc} "
        "Inspect before changing anything. Prefer small reversible changes, preserve data and secrets, "
        "verify the result, and report concise findings to the parent JARVIS agent. "
        "Follow the active GE360 AGENTS.md safety policy."
    )
    p.write_text("\n".join([
        f"name = {json.dumps(aid, ensure_ascii=False)}",
        f"description = {json.dumps(desc, ensure_ascii=False)}",
        f"developer_instructions = {json.dumps(instructions, ensure_ascii=False)}",
        ""
    ]), encoding="utf-8")
    print(f"[OK] Nuovo subagente creato: {aid}")
    print(f"File: {p}")
    print("Apri una nuova sessione JARVIS per caricarlo.")
else:
    raise SystemExit("Comandi: list, add")
