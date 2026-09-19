from __future__ import annotations

import shutil
import subprocess


def _run(args: list[str], timeout: int = 8) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def codex_status() -> dict:
    binary = shutil.which("codex")
    if not binary:
        return {
            "installed": False,
            "binary": None,
            "version": None,
            "authenticated": False,
            "auth": "Codex CLI non trovato",
        }

    _, version = _run([binary, "--version"])
    code, auth = _run([binary, "login", "status"])
    return {
        "installed": True,
        "binary": binary,
        "version": version or "unknown",
        "authenticated": code == 0,
        "auth": auth or ("login ok" if code == 0 else "login richiesto"),
    }
