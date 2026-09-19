#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${GE360_AGENT_HOME:-/opt/ge360-agent-control}"
RUN_USER="${SUDO_USER:-$USER}"
RUN_GROUP="$(id -gn "$RUN_USER")"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"

if [ -z "$RUN_HOME" ]; then
  echo "Impossibile determinare la home di $RUN_USER"
  exit 1
fi

if [ "$(id -u)" -eq 0 ]; then
  SUDO=()
  AS_USER=(runuser -u "$RUN_USER" --)
else
  SUDO=(sudo)
  AS_USER=()
fi

echo "======================================"
echo " GE360 JARVIS · INSTALLAZIONE DEBIAN"
echo "======================================"
echo "Utente: $RUN_USER"
echo "Destinazione: $DEST"

"${SUDO[@]}" apt-get update
"${SUDO[@]}" apt-get install -y python3 python3-venv python3-pip tmux git curl rsync ca-certificates

"${SUDO[@]}" mkdir -p "$DEST" /etc/ge360-agent
printf '%s\n' "$SOURCE" | "${SUDO[@]}" tee /etc/ge360-agent/source_path >/dev/null
"${SUDO[@]}" rsync -a --delete --exclude '.git/' --exclude '.venv/' --exclude 'runtime/' "$SOURCE/" "$DEST/"
"${SUDO[@]}" chown -R "$RUN_USER:$RUN_GROUP" "$DEST"

if [ ! -f /etc/ge360-agent/config.toml ]; then
  tmp="$(mktemp)"
  sed "s|/home/jarvis|$RUN_HOME|g" "$DEST/config/ge360.toml" > "$tmp"
  "${SUDO[@]}" install -m 0644 "$tmp" /etc/ge360-agent/config.toml
  rm -f "$tmp"
  echo "[OK] Config creata in /etc/ge360-agent/config.toml"
else
  echo "[OK] Config esistente preservata."
fi

if [ ! -d "$DEST/.venv" ]; then
  "${AS_USER[@]}" python3 -m venv "$DEST/.venv"
fi
"${AS_USER[@]}" "$DEST/.venv/bin/python" -m pip install --upgrade pip
"${AS_USER[@]}" "$DEST/.venv/bin/pip" install -r "$DEST/requirements.txt"

"${AS_USER[@]}" mkdir -p "$RUN_HOME/.agents/skills" "$RUN_HOME/.codex"
"${AS_USER[@]}" rsync -a "$DEST/.agents/skills/" "$RUN_HOME/.agents/skills/"

GLOBAL_AGENTS="$RUN_HOME/.codex/AGENTS.md"
MARKER="GE360-JARVIS-GLOBAL-POLICY"
if ! "${AS_USER[@]}" grep -q "$MARKER" "$GLOBAL_AGENTS" 2>/dev/null; then
  {
    echo
    echo "<!-- $MARKER BEGIN -->"
    cat "$DEST/AGENTS.md"
    echo "<!-- $MARKER END -->"
  } | "${SUDO[@]}" tee -a "$GLOBAL_AGENTS" >/dev/null
  "${SUDO[@]}" chown "$RUN_USER:$RUN_GROUP" "$GLOBAL_AGENTS"
  echo "[OK] Policy GE360 aggiunta a ~/.codex/AGENTS.md"
else
  echo "[OK] Policy GE360 già presente."
fi

if ! "${AS_USER[@]}" bash -lc 'export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"; command -v codex >/dev/null 2>&1'; then
  echo "[GE360] Installazione Codex CLI ufficiale..."
  "${AS_USER[@]}" bash -lc 'curl -fsSL https://chatgpt.com/codex/install.sh | sh'
fi

unit_tmp="$(mktemp)"
sed -e "s|__USER__|$RUN_USER|g" -e "s|__GROUP__|$RUN_GROUP|g" -e "s|__HOME__|$RUN_HOME|g" -e "s|__ROOT__|$DEST|g" "$DEST/systemd/ge360-agent-control.service.in" > "$unit_tmp"
"${SUDO[@]}" install -m 0644 "$unit_tmp" /etc/systemd/system/ge360-agent-control.service
rm -f "$unit_tmp"

"${SUDO[@]}" chmod +x "$DEST/scripts/"*.sh
"${SUDO[@]}" ln -sfn "$DEST/scripts/jarvis.sh" /usr/local/bin/jarvis
"${SUDO[@]}" systemctl daemon-reload
"${SUDO[@]}" systemctl enable --now ge360-agent-control.service

echo
echo "======================================"
echo " INSTALLAZIONE COMPLETATA"
echo "======================================"
echo "Dashboard: http://127.0.0.1:8789"
echo "Super terminale: jarvis"
echo "Login ChatGPT/Codex: jarvis login"
echo

"${AS_USER[@]}" "$DEST/scripts/doctor.sh" || true

if ! "${AS_USER[@]}" bash -lc 'export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"; codex login status >/dev/null 2>&1'; then
  echo
  echo "[AZIONE NECESSARIA UNA SOLA VOLTA]"
  echo "Esegui: jarvis login"
  echo "Poi completa il login ChatGPT con il codice dispositivo."
fi
