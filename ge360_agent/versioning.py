from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import subprocess


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    schema_version: int
    channel: str


def release_info() -> ReleaseInfo:
    path = ROOT / "release.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return ReleaseInfo(
        version=str(data.get("version", "0.0.0")),
        schema_version=int(data.get("schema_version", 0)),
        channel=str(data.get("channel", "stable")),
    )


def git_commit(path: Path | None = None) -> str:
    cwd = path or ROOT
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--short=12", "HEAD"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""
