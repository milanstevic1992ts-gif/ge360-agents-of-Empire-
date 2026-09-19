#!/usr/bin/env bash
set -u

ROOT="${GE360_AGENT_HOME:-/opt/ge360-agent-control}"
PORT="${GE360_AGENT_PORT:-8789}"
FAIL=0

ok(){ printf '[OK]   %s\n' "$1"; }
warn(){ printf '[WARN] %s\n' "$1"; }
fail(){ printf '[FAIL] %s\n' "$1"; FAIL=1; }

echo "GE360 JARVIS DOCTOR"
echo "==================="

for cmd in python3 tmux git curl; do
  if command -v "$cmd" >/dev/null 2>&1; then ok "$cmd presente"; else fail "$cmd mancante"; fi
done

if command -v docker >/dev/null 2>&1; then
  if docker ps >/dev/null 2>&1; then ok "Docker accessibile"; else warn "Docker presente ma non accessibile all'utente"; fi
else
  warn "Docker non installato (va bene se non serve su questo host)"
fi

if command -v codex >/dev/null 2>&1; then
  ok "$(codex --version 2>/dev/null || echo 'Codex presente')"
  if codex login status >/dev/null 2>&1; then ok "Codex login attivo"; else warn "Codex richiede login: esegui jarvis login"; fi
else
  fail "Codex CLI mancante"
fi

if [ -x "$ROOT/.venv/bin/python" ]; then
  if "$ROOT/.venv/bin/python" -c 'import fastapi, uvicorn, ge360_agent.main' >/dev/null 2>&1; then
    ok "Backend Python importabile"
  else
    fail "Backend Python non importabile"
  fi
else
  fail "Virtualenv non trovato in $ROOT/.venv"
fi

if [ -f /etc/ge360-agent/config.toml ]; then ok "Configurazione presente"; else warn "Configurazione /etc/ge360-agent/config.toml mancante"; fi

if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet ge360-agent-control.service; then
    ok "ge360-agent-control.service attivo"
  else
    warn "ge360-agent-control.service non attivo"
  fi
fi

if curl -fsS --max-time 3 "http://127.0.0.1:${PORT}/api/status" >/dev/null 2>&1; then
  ok "Dashboard API risponde su 127.0.0.1:${PORT}"
else
  warn "Dashboard API non raggiungibile (o token richiesto)"
fi

if [ "$FAIL" -eq 0 ]; then
  echo
  echo "Doctor completato: nessun errore bloccante rilevato."
else
  echo
  echo "Doctor completato: ci sono errori da correggere."
fi
exit "$FAIL"
