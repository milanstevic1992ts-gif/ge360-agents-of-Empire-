#!/usr/bin/env bash
set -Eeuo pipefail

DEST="${GE360_AGENT_HOME:-/opt/ge360-agent-control}"
PURGE="${1:-}"

sudo systemctl disable --now ge360-agent-control.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/ge360-agent-control.service
sudo systemctl daemon-reload
sudo rm -f /usr/local/bin/jarvis

echo "Servizio GE360 Agent Control Center rimosso."

if [ "$PURGE" = "--purge" ]; then
  sudo rm -rf "$DEST"
  rm -rf "$HOME/.agents/skills/ge360-system-admin" "$HOME/.agents/skills/ge360-docker-doctor" "$HOME/.agents/skills/ge360-service-recovery" "$HOME/.agents/skills/ge360-safe-deploy"
  echo "File applicazione e skill GE360 rimossi."
else
  echo "Configurazione, autenticazione Codex, skill e file in $DEST sono stati preservati."
  echo "Usa --purge solo se vuoi rimuovere anche l'installazione applicativa."
fi
