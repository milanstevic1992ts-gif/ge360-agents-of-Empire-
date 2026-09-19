from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import tomllib


_AGENT_ID = re.compile(r"^[a-z][a-z0-9_-]{1,39}$")


@dataclass(frozen=True)
class AgentProfile:
    id: str
    name: str
    description: str
    instructions: str
    path: Path


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()


def agents_dir() -> Path:
    path = codex_home() / "agents"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_agent(path: Path) -> AgentProfile | None:
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return None

    name = str(data.get("name", path.stem)).strip() or path.stem
    description = str(data.get("description", "")).strip()
    instructions = str(data.get("developer_instructions", "")).strip()
    return AgentProfile(
        id=path.stem,
        name=name,
        description=description,
        instructions=instructions,
        path=path,
    )


def list_agents() -> list[AgentProfile]:
    result: list[AgentProfile] = []
    for path in sorted(agents_dir().glob("*.toml")):
        profile = _read_agent(path)
        if profile:
            result.append(profile)
    return result


def create_agent(agent_id: str, description: str) -> AgentProfile:
    agent_id = agent_id.strip().lower()
    description = description.strip()
    if not _AGENT_ID.fullmatch(agent_id):
        raise ValueError("ID agente non valido: usa minuscole, numeri, - o _, iniziando con una lettera")
    if not description:
        raise ValueError("Descrizione agente obbligatoria")

    path = agents_dir() / f"{agent_id}.toml"
    if path.exists():
        raise ValueError(f"L'agente {agent_id} esiste già")

    instructions = (
        f"You are the GE360 specialist named {agent_id}. Your domain is: {description} "
        "Inspect before changing anything. Prefer small reversible changes, preserve data and secrets, "
        "verify the result, and return concise findings to the parent JARVIS agent. "
        "Follow the active GE360 AGENTS.md safety policy."
    )

    content = "\n".join(
        [
            f"name = {json.dumps(agent_id, ensure_ascii=False)}",
            f"description = {json.dumps(description, ensure_ascii=False)}",
            f"developer_instructions = {json.dumps(instructions, ensure_ascii=False)}",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
    return _read_agent(path) or AgentProfile(agent_id, agent_id, description, instructions, path)
