# Changelog

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
