from __future__ import annotations

import json
import selectors
import shutil
import subprocess
import time


def probe_threads(timeout: float = 2.5) -> dict:
    codex = shutil.which("codex")
    if not codex:
        return {"available": False, "reason": "codex_not_found", "threads": []}

    proc = None
    try:
        proc = subprocess.Popen(
            [codex, "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if not proc.stdin or not proc.stdout:
            return {"available": False, "reason": "stdio_unavailable", "threads": []}

        messages = [
            {
                "method": "initialize",
                "id": 1,
                "params": {
                    "clientInfo": {
                        "name": "ge360_jarvis",
                        "title": "GE360 JARVIS",
                        "version": "0.5.0",
                    }
                },
            },
            {"method": "initialized", "params": {}},
            {
                "method": "thread/list",
                "id": 20,
                "params": {
                    "cursor": None,
                    "limit": 30,
                    "sortKey": "updated_at",
                    "sortDirection": "desc",
                    "sourceKinds": [
                        "cli",
                        "appServer",
                        "subAgent",
                        "subAgentThreadSpawn",
                        "subAgentOther",
                    ],
                },
            },
        ]
        for message in messages:
            proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            proc.stdin.flush()

        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + timeout
        seen_init = False
        while time.monotonic() < deadline:
            events = selector.select(timeout=max(0.05, deadline - time.monotonic()))
            if not events:
                continue
            line = proc.stdout.readline()
            if not line:
                break
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == 1 and "result" in msg:
                seen_init = True
            if msg.get("id") == 20:
                if "error" in msg:
                    return {
                        "available": seen_init,
                        "reason": "thread_list_error",
                        "error": msg.get("error"),
                        "threads": [],
                    }
                result = msg.get("result") or {}
                return {
                    "available": True,
                    "protocol": "stdio",
                    "experimental_transport": False,
                    "threads": result.get("data") or [],
                    "next_cursor": result.get("nextCursor"),
                }

        return {
            "available": seen_init,
            "reason": "timeout",
            "threads": [],
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "reason": str(exc), "threads": []}
    finally:
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=0.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
