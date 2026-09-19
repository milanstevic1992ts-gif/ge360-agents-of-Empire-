---
name: ge360-docker-doctor
description: Diagnose Docker and Docker Compose failures on the GE360 Debian host, including unhealthy containers, restart loops, ports, networks, volumes and compose configuration. Use when Mautic, n8n, SuiteCRM, Prospex or another containerized service is down.
---

Use a non-destructive Docker troubleshooting sequence.

1. Locate the correct compose project and compose file.
2. Run compose config validation.
3. Inspect compose ps and container health.
4. Read only the relevant recent logs.
5. Check port conflicts, mounts, permissions, environment presence and dependency health.
6. Back up changed compose/config files.
7. Apply the smallest fix.
8. Recreate or restart only affected services.
9. Verify container health and the actual HTTP/TCP endpoint.

Never run docker system prune, delete volumes, remove database data, or replace an .env file blindly.
