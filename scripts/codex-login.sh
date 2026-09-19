#!/usr/bin/env bash
set -Eeuo pipefail

export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

if ! command -v codex >/dev/null 2>&1; then
  echo "[GE360] Codex CLI non trovato. Installazione dal canale ufficiale OpenAI..."
  curl -fsSL https://chatgpt.com/codex/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "[GE360] Versione:"
codex --version || true

STATUS="$(codex login status 2>&1 || true)"
if [ -n "$STATUS" ]; then
  if printf "%s" "$STATUS" | grep -Eqi "api[ -]?key"; then
    echo "[WARN] Codex risulta autenticato con API key (può generare costi API separati)."
    printf "Passare al login ChatGPT incluso nel piano? [S/n] "
    read -r answer
    case "${answer:-S}" in
      n|N|no|NO) echo "$STATUS"; exit 0 ;;
      *) codex logout || true ;;
    esac
  elif printf "%s" "$STATUS" | grep -qi "chatgpt"; then
    echo "[OK] Codex è già autenticato con ChatGPT."
    echo "$STATUS"
    exit 0
  elif codex login status >/dev/null 2>&1; then
    echo "[OK] Codex è già autenticato (metodo non riconosciuto automaticamente)."
    echo "$STATUS"
    exit 0
  fi
fi

echo "[GE360] Login ChatGPT con codice dispositivo."
echo "Apri il link mostrato da Codex sul telefono/computer e inserisci il codice."
if ! codex login --device-auth; then
  echo "[GE360] Device auth non disponibile. Passo al login interattivo."
  codex login
fi

echo
codex login status
