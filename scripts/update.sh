#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${GE360_AGENT_HOME:-/opt/ge360-agent-control}"
SOURCE_PATH="$(cat /etc/ge360-agent/source_path 2>/dev/null || true)"
BACKUP_ROOT="$HOME/.local/share/ge360-jarvis/backups"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BACKUP_ROOT/$STAMP"

if [ -z "$SOURCE_PATH" ] || [ ! -d "$SOURCE_PATH/.git" ]; then
  echo "[FAIL] Checkout sorgente non trovato."
  echo "Reinstalla una volta da una clone Git e poi gli update saranno automatici."
  exit 1
fi

if [ -n "$(git -C "$SOURCE_PATH" status --porcelain)" ]; then
  echo "[FAIL] La repo sorgente contiene modifiche locali:"
  git -C "$SOURCE_PATH" status --short
  exit 1
fi

CURRENT_VERSION="$(cat "$ROOT/VERSION" 2>/dev/null || echo unknown)"
CURRENT_COMMIT="$(git -C "$SOURCE_PATH" rev-parse HEAD)"

mkdir -p "$BACKUP"
printf "%s\n" "$CURRENT_COMMIT" > "$BACKUP/source-commit"
printf "%s\n" "$CURRENT_VERSION" > "$BACKUP/version"

echo "[BACKUP] $BACKUP"
if [ -d "$ROOT" ]; then
  sudo tar -C "$(dirname "$ROOT")" --exclude="ge360-agent-control/.venv" -czf "$BACKUP/installed-code.tgz" "$(basename "$ROOT")"
fi
if [ -d /etc/ge360-agent ]; then
  sudo tar -C /etc -czf "$BACKUP/etc-ge360-agent.tgz" ge360-agent
fi
if [ -d "$HOME/.codex/agents" ]; then
  tar -C "$HOME/.codex" -czf "$BACKUP/codex-agents.tgz" agents
fi
if [ -d "$HOME/.agents/skills" ]; then
  tar -C "$HOME/.agents" -czf "$BACKUP/skills.tgz" skills
fi

echo "[UPDATE] Recupero aggiornamenti..."
git -C "$SOURCE_PATH" fetch --prune origin
git -C "$SOURCE_PATH" pull --ff-only

TARGET_VERSION="$(cat "$SOURCE_PATH/VERSION" 2>/dev/null || echo unknown)"
echo "[UPDATE] $CURRENT_VERSION -> $TARGET_VERSION"

bash "$SOURCE_PATH/scripts/install.sh"

echo "[VERIFY] Controllo installazione..."
if "$ROOT/scripts/doctor.sh"; then
  echo
  echo "[OK] Aggiornamento completato: $TARGET_VERSION"
  echo "Backup rollback: $BACKUP"
else
  echo
  echo "[FAIL] Doctor fallito dopo l aggiornamento."
  echo "Backup: $BACKUP"
  echo "Rollback: jarvis rollback $STAMP"
  exit 2
fi
