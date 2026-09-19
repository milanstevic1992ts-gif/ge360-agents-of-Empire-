# Installazione Debian

## Prima installazione

Clona la repository con il tuo normale accesso GitHub e poi esegui:

    cd ge360-agents-of-Empire-
    bash scripts/install.sh

L'installer:
- installa dipendenze Debian leggere;
- copia il runtime in /opt/ge360-agent-control;
- crea una virtualenv Python;
- installa Codex CLI dal canale ufficiale se manca;
- installa le skill GE360 nell'utente;
- aggiunge la policy GE360 a ~/.codex/AGENTS.md in modo idempotente;
- crea e avvia ge360-agent-control.service;
- crea il comando /usr/local/bin/jarvis;
- esegue il doctor.

## Login

Una sola volta:

    jarvis login

Su Debian headless viene usato prima il login con codice dispositivo. Apri sul telefono/computer il link mostrato e completa l'accesso ChatGPT.

Controllo:

    codex login status

## Uso

Super terminale:

    jarvis

La sessione vive dentro tmux. Se cade SSH, rilancia jarvis e rientri nella stessa sessione.

Dashboard:

    http://127.0.0.1:8789

Doctor:

    jarvis doctor

Aggiornamento:

    jarvis update

L'aggiornamento si ferma se la checkout sorgente contiene modifiche locali, per non cancellare lavoro non salvato.

## Accesso da telefono

Non esporre direttamente la porta 8789 su Internet. Usa Tailscale o un reverse proxy privato. Se cambi il bind da 127.0.0.1, imposta anche GE360_AGENT_TOKEN con un valore forte nel servizio.

## Configurazione

File:

    /etc/ge360-agent/config.toml

Aggiungi qui workspaces e unit systemd da visualizzare. La dashboard accetta solo workspace definiti in questo file.
