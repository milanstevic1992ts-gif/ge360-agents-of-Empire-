---
name: ge360-safe-deploy
description: Safely install or update a GE360 repository/app on Debian using Git, Python, Node, Docker or systemd while protecting existing services and data. Use for "installa questa repo", "aggiorna", "pubblica", "metti sul Debian".
---

Before deployment:
- inspect the target path and git status;
- identify current listening ports and existing service names;
- identify persistent data and secrets;
- create a rollback checkpoint for files being replaced.

Prefer an isolated virtual environment/container and an unused port. Do not overwrite an existing app merely because its name is similar.

For updates, preserve local configuration and secrets. Run syntax/config tests before restart. Start the new version, verify health, then retire the old process if needed.

Report the final path, service name, port/URL, version/commit and rollback location.
