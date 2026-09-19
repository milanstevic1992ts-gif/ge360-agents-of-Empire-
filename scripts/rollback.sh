#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${GE360_AGENT_HOME:-/opt/ge360-agent-control}"
SOURCE_PATH="$(cat /etc/ge360-agent/source_path 2>/dev/null || true)"
BACKUP_ROOT="$HOME/.local/share/ge360-jarvis/backups"
ID="${1:-}"

if [ -z "$ID" ]; then
  echo "Backup disponibili:"
  find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -printf "%f\n" 2>/dev/null | sort -r | head -20
  echo "Uso: jarvis rollback YYYYMMDD-HHMMSS"
  exit 1
fi

BACKUP="$BACKUP_ROOT/$ID"
[ -d "$BACKUP" ] || { echo "[FAIL] Backup non trovato: $BACKUP"; exit 1; }

echo "[ROLLBACK] Ripristino $ID"
sudo systemctl stop ge360-agent-control.service 2>/dev/null || true

if [ -f "$BACKUP/installed-code.tgz" ]; then
  sudo rm -rf "$ROOT"
  sudo mkdir -p "$(dirname "$ROOT")"
  sudo tar -C "$(dirname "$ROOT")" -xzf "$BACKUP/installed-code.tgz"
  sudo chown -R "$USER:$(id -gn)" "$ROOT"
fi

if [ -f "$BACKUP/etc-ge360-agent.tgz" ]; then
  sudo rm -rf /etc/ge360-agent
  sudo tar -C /etc -xzf "$BACKUP/etc-ge360-agent.tgz"
fi

if [ -f "$BACKUP/codex-agents.tgz" ]; then
  mkdir -p "$HOME/.codex"
  rm -rf "$HOME/.codex/agents"
  tar -C "$HOME/.codex" -xzf "$BACKUP/codex-agents.tgz"
fi

if [ -f "$BACKUP/skills.tgz" ]; then
  mkdir -p "$HOME/.agents"
  rm -rf "$HOME/.agents/skills"
  tar -C "$HOME/.agents" -xzf "$BACKUP/skills.tgz"
fi

if [ -f "$BACKUP/source-commit" ] && [ -d "$SOURCE_PATH/.git" ]; then
  COMMIT="$(cat "$BACKUP/source-commit")"
  git -C "$SOURCE_PATH" reset --hard "$COMMIT"
fi

if [ -x "$ROOT/.venv/bin/pip" ]; then
  "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
else
  python3 -m venv "$ROOT/.venv"
  "$ROOT/.venv/bin/pip" install -r "$ROOT/requirements.txt"
fi

sudo chmod +x "$ROOT/scripts/"*.sh
sudo ln -sfn "$ROOT/scripts/jarvis.sh" /usr/local/bin/jarvis
sudo systemctl daemon-reload
sudo systemctl enable --now ge360-agent-control.service
sleep 2

echo "[OK] Rollback completato."
"$ROOT/scripts/doctor.sh" || true
