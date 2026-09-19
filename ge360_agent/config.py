from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import tomllib


@dataclass(frozen=True)
class Workspace:
    id: str
    name: str
    path: Path


@dataclass
class Settings:
    host: str = "127.0.0.1"
    port: int = 8789
    session_prefix: str = "ge360-"
    codex_command: str = "codex"
    token: str = ""
    workspaces: list[Workspace] = field(default_factory=list)
    systemd_units: list[str] = field(default_factory=list)


def _default_config_path() -> Path:
    env = os.getenv("GE360_AGENT_CONFIG")
    if env:
        return Path(env).expanduser()
    system = Path("/etc/ge360-agent/config.toml")
    if system.exists():
        return system
    return Path(__file__).resolve().parents[1] / "config" / "ge360.toml"


def load_settings(path: Path | None = None) -> Settings:
    cfg_path = path or _default_config_path()
    data: dict = {}
    if cfg_path.exists():
        with cfg_path.open("rb") as fh:
            data = tomllib.load(fh)

    server = data.get("server", {})
    codex = data.get("codex", {})
    services = data.get("services", {})

    workspaces: list[Workspace] = []
    for item in data.get("workspaces", []):
        raw_path = os.path.expandvars(os.path.expanduser(str(item["path"])))
        workspaces.append(
            Workspace(
                id=str(item["id"]),
                name=str(item.get("name", item["id"])),
                path=Path(raw_path).resolve(),
            )
        )

    if not workspaces:
        fallback = Path(os.getenv("GE360_WORKSPACE", "/opt/ge360")).expanduser()
        if not fallback.exists():
            fallback = Path.home()
        workspaces = [Workspace("ge360", "GE360", fallback.resolve())]

    return Settings(
        host=str(server.get("host", "127.0.0.1")),
        port=int(server.get("port", 8789)),
        session_prefix=str(server.get("session_prefix", "ge360-")),
        codex_command=str(codex.get("command", "codex")),
        token=os.getenv("GE360_AGENT_TOKEN", str(server.get("token", ""))),
        workspaces=workspaces,
        systemd_units=[str(x) for x in services.get("systemd_units", [])],
    )
