from __future__ import annotations

from dataclasses import dataclass
import shlex
import shutil
import subprocess
import time

from .security import validate_session_name


class TmuxError(RuntimeError):
    pass


@dataclass
class Session:
    name: str
    created: int
    attached: bool


def _tmux(args: list[str], timeout: int = 8, check: bool = True) -> subprocess.CompletedProcess[str]:
    binary = shutil.which("tmux")
    if not binary:
        raise TmuxError("tmux non installato")
    proc = subprocess.run(
        [binary, *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if check and proc.returncode != 0:
        raise TmuxError(proc.stderr.strip() or proc.stdout.strip() or "errore tmux")
    return proc


class TmuxManager:
    def __init__(self, prefix: str = "ge360-") -> None:
        self.prefix = prefix

    def _full_name(self, short_name: str) -> str:
        return self.prefix + validate_session_name(short_name)

    def _assert_managed(self, full_name: str) -> None:
        if not full_name.startswith(self.prefix):
            raise TmuxError("sessione non gestita da GE360")

    def list(self) -> list[Session]:
        proc = _tmux(
            ["list-sessions", "-F", "#{session_name}\t#{session_created}\t#{session_attached}"],
            check=False,
        )
        if proc.returncode != 0:
            return []
        result: list[Session] = []
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) != 3 or not parts[0].startswith(self.prefix):
                continue
            result.append(
                Session(
                    name=parts[0],
                    created=int(parts[1] or 0),
                    attached=parts[2] == "1",
                )
            )
        return result

    def create(self, short_name: str, cwd: str, command: str) -> str:
        name = self._full_name(short_name)
        exists = _tmux(["has-session", "-t", name], check=False)
        if exists.returncode == 0:
            raise TmuxError(f"La sessione {name} esiste già")
        cmd = shlex.split(command)
        if not cmd:
            raise TmuxError("comando Codex vuoto")
        _tmux(["new-session", "-d", "-s", name, "-c", cwd, "--", *cmd], timeout=12)
        time.sleep(0.25)
        return name

    def send(self, full_name: str, message: str) -> None:
        self._assert_managed(full_name)
        if not message.strip():
            raise TmuxError("messaggio vuoto")
        buffer_name = f"{full_name}-prompt"
        _tmux(["set-buffer", "-b", buffer_name, "--", message])
        _tmux(["paste-buffer", "-b", buffer_name, "-t", full_name, "-d"])
        _tmux(["send-keys", "-t", full_name, "Enter"])

    def capture(self, full_name: str, lines: int = 180) -> str:
        self._assert_managed(full_name)
        lines = max(20, min(lines, 1000))
        proc = _tmux(["capture-pane", "-p", "-J", "-S", f"-{lines}", "-t", full_name])
        return proc.stdout

    def stop(self, full_name: str) -> None:
        self._assert_managed(full_name)
        _tmux(["kill-session", "-t", full_name])
