# Changelog

## 0.7.0

### JARVIS Chat
- Codex App Server diventa il motore della chat strutturata via stdio JSON-RPC;
- streaming live al browser via SSE;
- cronologia conversazioni persistente in SQLite;
- messaggi utente/JARVIS separati e stato live working / waiting / error / idle;
- tool call, reasoning e piani mostrati come card invece di output terminale grezzo;
- approvazioni comando/file direttamente nella chat;
- richieste di input Codex mostrate nella conversazione;
- allegati riutilizzati nel composer chat;
- pulsante Stop per interrompere il turno;
- recupero dalla cronologia persistente se un evento streaming viene perso;
- tmux resta disponibile come modalità avanzata e fallback.

### Runtime
- schema runtime 3: chat_threads, chat_messages e chat_server_requests;
- test per delta streaming e approval request;
- doctor e CI validano anche chat.js e il modulo chat.


## 0.5.0

### Update system
- explicit VERSION and release.json manifest;
- schema-versioned runtime migrations;
- automatic backup before update;
- transactional update flow through `jarvis update`;
- rollback snapshots through `jarvis rollback`;
- `jarvis version`;
- doctor checks for migrations, updater and rollback;
- CI validates migration and update scripts.

### Agent observability
- persistent `agent_activity` event store;
- agent status: ready / working / waiting / done / error;
- dashboard timeline;
- release version visible in dashboard;
- Smart Router records primary agent and queued collaborators.

### Codex App Server
- optional stdio probe adapter;
- manual API probe endpoint;
- architecture prepared to adopt structured `thread/status/changed` and subagent events later without replacing the dashboard.

## 0.4.1
- stale dashboard cache protection;
- cache-busted CSS/JS assets.

## 0.4.0
- seven-agent dashboard;
- dedicated n8n Engineer;
- Smart Router, playbooks and operational memory;
- model and reasoning controls.
