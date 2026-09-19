#!/usr/bin/env bash
set -Eeuo pipefail

export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
ROOT="${GE360_AGENT_HOME:-/opt/ge360-agent-control}"
SESSION="${GE360_JARVIS_SESSION:-ge360-jarvis}"
WORKSPACE="${GE360_WORKSPACE:-/opt/ge360}"
[ -d "$WORKSPACE" ] || WORKSPACE="$HOME"

usage(){
  cat <<'EOF'
JARVIS GE360

Uso:
  jarvis                 apre/riprende il super terminale Codex
  jarvis web             mostra indirizzo dashboard
  jarvis status          stato servizio
  jarvis sessions        sessioni agenti
  jarvis doctor          diagnostica installazione
  jarvis login           login Codex con ChatGPT
  jarvis restart         riavvia dashboard
  jarvis stop            ferma la sessione terminale jarvis
EOF
}

cmd="${1:-terminal}"
case "$cmd" in
  terminal)
    if ! command -v tmux >/dev/null 2>&1; then
      echo "tmux non installato. Esegui scripts/install.sh"
      exit 1
    fi
    if ! command -v codex >/dev/null 2>&1; then
      echo "Codex non installato. Esegui: jarvis login"
      exit 1
    fi
    if tmux has-session -t "$SESSION" 2>/dev/null; then
      exec tmux attach-session -t "$SESSION"
    fi
    exec tmux new-session -s "$SESSION" -c "$WORKSPACE" "codex --search"
    ;;
  web)
    echo "Dashboard locale: http://127.0.0.1:8789"
    echo "Per accesso remoto usa una rete privata/Tailscale e proteggi l'API con GE360_AGENT_TOKEN."
    ;;
  status)
    systemctl --no-pager --full status ge360-agent-control.service || true
    ;;
  sessions)
    tmux list-sessions 2>/dev/null | grep '^ge360-' || echo "Nessuna sessione GE360 attiva."
    ;;
  doctor)
    exec "$ROOT/scripts/doctor.sh"
    ;;
  login)
    exec "$ROOT/scripts/codex-login.sh"
    ;;
  restart)
    sudo systemctl restart ge360-agent-control.service
    systemctl --no-pager --full status ge360-agent-control.service || true
    ;;
  stop)
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    echo "Sessione $SESSION fermata."
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    usage
    exit 2
    ;;
esac
