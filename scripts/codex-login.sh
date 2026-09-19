#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${GE360_AGENT_HOME:-/opt/ge360-agent-control}"
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"

mkdir -p "$CODEX_HOME"
chmod 700 "$CODEX_HOME" 2>/dev/null || true

if [ -x "$ROOT/scripts/configure-codex.py" ]; then
  python3 "$ROOT/scripts/configure-codex.py"
fi

if ! command -v codex >/dev/null 2>&1; then
  echo "[GE360] Codex CLI non trovato. Installazione ufficiale OpenAI..."
  curl -fsSL https://chatgpt.com/codex/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "[GE360] Codex: $(codex --version 2>/dev/null || echo installato)"
echo "[GE360] CODEX_HOME: $CODEX_HOME"

STATUS="$(codex login status 2>&1 || true)"
if codex login status >/dev/null 2>&1; then
  echo "[OK] Codex è già autenticato."
  echo "$STATUS"
else
  echo
  echo "[GE360] Login ChatGPT con codice dispositivo."
  echo "Apri il link mostrato e inserisci il codice monouso."
  echo
  codex login --device-auth
fi

echo
echo "===== VERIFICA LOGIN ====="
codex login status

if [ -f "$CODEX_HOME/auth.json" ]; then
  chmod 600 "$CODEX_HOME/auth.json" 2>/dev/null || true
  echo "[OK] Login persistente salvato in $CODEX_HOME/auth.json"
else
  echo "[WARN] auth.json non trovato. Controllo comunque lo stato restituito da Codex."
fi

echo
echo "===== RIAVVIO JARVIS ====="
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl restart ge360-agent-control.service
  sleep 2
fi

echo
echo "===== VERIFICA JARVIS ====="
if command -v curl >/dev/null 2>&1; then
  curl -fsS http://127.0.0.1:8789/api/status 2>/dev/null | python3 -c '
import json,sys
try:
    d=json.load(sys.stdin)
    c=d.get("codex",{})
    print("installed:", c.get("installed"))
    print("authenticated:", c.get("authenticated"))
    print("billing_mode:", c.get("billing_mode"))
    print("auth:", c.get("auth"))
except Exception as e:
    print("Dashboard API non verificabile:", e)
' || true
fi
