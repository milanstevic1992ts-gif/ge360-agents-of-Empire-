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
  if (cd "$ROOT" && "$ROOT/.venv/bin/python" -c 'import fastapi, uvicorn, ge360_agent.main, ge360_agent.smart, ge360_agent.activity, ge360_agent.appserver, ge360_agent.versioning') >/dev/null 2>&1; then
    ok "Backend + Smart Router + update modules importabili"
  else
    fail "Backend Python o Smart Router non importabile"
  fi

  if (cd "$ROOT" && "$ROOT/.venv/bin/python" -m unittest discover -s tests -q) >/dev/null 2>&1; then
    ok "Test Python superati"
  else
    fail "Test Python falliti"
  fi
else
  fail "Virtualenv non trovato in $ROOT/.venv"
fi

AGENT_COUNT="$(find "$HOME/.codex/agents" -maxdepth 1 -type f -name '*.toml' 2>/dev/null | wc -l | tr -d ' ')"
if [ "${AGENT_COUNT:-0}" -ge 7 ]; then
  ok "$AGENT_COUNT subagenti Codex installati"
else
  warn "Trovati solo ${AGENT_COUNT:-0} subagenti Codex"
fi

if [ -f "$HOME/.codex/agents/ge360-n8n-engineer.toml" ]; then
  ok "n8n Engineer installato"
else
  fail "Profilo ge360-n8n-engineer mancante"
fi

if [ -f "$HOME/.agents/skills/ge360-n8n-engineer/SKILL.md" ]; then
  ok "Skill n8n Engineer installata"
else
  fail "Skill ge360-n8n-engineer mancante"
fi

RECIPE_COUNT="$(find "$ROOT/recipes" -maxdepth 1 -type f -name '*.toml' 2>/dev/null | wc -l | tr -d ' ')"
if [ "${RECIPE_COUNT:-0}" -ge 7 ]; then
  ok "$RECIPE_COUNT playbook Smart disponibili"
else
  warn "Playbook Smart mancanti o incompleti"
fi

if command -v node >/dev/null 2>&1; then
  if node --check "$ROOT/web/app.js" >/dev/null 2>&1; then
    ok "JavaScript dashboard valido"
  else
    fail "Errore sintassi in web/app.js"
  fi
else
  warn "node non presente: controllo sintassi JavaScript saltato"
fi

if [ -f "$ROOT/VERSION" ] && [ -f "$ROOT/release.json" ]; then
  ok "Versioning release presente: $(cat "$ROOT/VERSION")"
else
  fail "VERSION/release.json mancanti"
fi

if "$ROOT/.venv/bin/python" "$ROOT/scripts/migrate.py" >/dev/null 2>&1; then
  ok "Migrazioni runtime allineate"
else
  fail "Migrazioni runtime fallite"
fi

if [ -x "$ROOT/scripts/update.sh" ] && [ -x "$ROOT/scripts/rollback.sh" ]; then
  ok "Updater e rollback installati"
else
  fail "Updater/rollback mancanti o non eseguibili"
fi

if codex app-server --help >/dev/null 2>&1; then
  ok "Codex App Server disponibile (provider opzionale)"
else
  warn "Codex App Server non disponibile in questa versione CLI"
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
