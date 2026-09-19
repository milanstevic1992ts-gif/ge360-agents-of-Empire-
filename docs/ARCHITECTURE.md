# GE360 Agent Control Center architecture

## Goal

Give a non-programmer one place to operate a Debian GE360 host using natural-language instructions while keeping the actual execution model inspectable and reversible.

## Components

### Codex CLI
The reasoning/execution agent. It runs as the normal Linux user, inherits that user's Codex login, reads the global GE360 AGENTS policy and can use GE360 skills.

### tmux
Persistence layer. A Codex process remains alive when SSH or the browser disconnects. The Web backend never emulates the Codex protocol; it interacts with the real terminal session.

### FastAPI control plane
A deliberately small service that:
- reports host health;
- reports configured systemd units;
- reports Docker containers;
- creates named Codex/tmux sessions in allow-listed workspaces;
- captures terminal output;
- sends a natural-language prompt into a managed session;
- stops managed sessions.

There is intentionally no arbitrary shell-execution HTTP endpoint.

### Web/mobile dashboard
Vanilla HTML/CSS/JavaScript. No Node build, database or frontend framework is required. It polls the lightweight API and shows terminal snapshots.

## Authentication

Codex authentication belongs to the Linux user and is not copied into this repository. GE360 checks it using codex login status.

On headless Debian, scripts/codex-login.sh prefers codex login --device-auth. The user completes the browser/device step once.

## Skills

Repository skills live under .agents/skills so Codex can discover them when run in this project. The installer also copies GE360 skills to the user-level $HOME/.agents/skills so they remain available when Codex starts in /opt/ge360 or another configured project.

## Safety boundary

The Web API can only target tmux sessions whose names have the GE360 prefix. Workspaces are selected by ID from config, not supplied as arbitrary filesystem paths from the browser.

Destructive system actions remain controlled by Codex permissions plus AGENTS.md policy. The project does not grant unrestricted passwordless sudo.

## Resource target

The control plane is one Python/Uvicorn worker, static web assets and tmux. No Redis, PostgreSQL, Node runtime or additional AI model is required.
