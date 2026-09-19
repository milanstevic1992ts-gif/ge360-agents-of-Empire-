---
name: ge360-service-recovery
description: Recover a named GE360 application or systemd service that is stopped, unhealthy or unreachable. Use for service outages and when the user names Mautic, n8n, SuiteCRM, Prospex, GE360 backend or another installed app.
---

Treat recovery as diagnosis plus verification, not merely a restart.

Map the named application to its real process, systemd unit or Docker Compose stack. Capture status and recent error logs first. Check dependencies such as database, Redis, filesystem permissions, DNS and ports.

Only restart after identifying a reasonable cause or establishing that a clean restart is the least risky next diagnostic step.

If configuration must change, back it up first. Preserve database volumes and user data.

Finish with an end-to-end check and state clearly whether the service is healthy, partially working or still failing.
