from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def _meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            number = int(value.strip().split()[0])
            values[key] = number * 1024
    except (OSError, ValueError):
        pass
    return values


def system_health() -> dict:
    mem = _meminfo()
    total = mem.get("MemTotal", 0)
    available = mem.get("MemAvailable", 0)
    disk = shutil.disk_usage("/")
    try:
        load1, load5, load15 = os.getloadavg()
    except OSError:
        load1 = load5 = load15 = 0.0

    uptime = 0.0
    try:
        uptime = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        pass

    return {
        "hostname": os.uname().nodename,
        "cpu_count": os.cpu_count() or 0,
        "load": [round(load1, 2), round(load5, 2), round(load15, 2)],
        "memory": {
            "total": total,
            "available": available,
            "used": max(0, total - available),
        },
        "disk": {
            "total": disk.total,
            "free": disk.free,
            "used": disk.used,
        },
        "uptime_seconds": int(uptime),
        "timestamp": int(time.time()),
    }


def systemd_status(units: list[str]) -> list[dict]:
    out: list[dict] = []
    systemctl = shutil.which("systemctl")
    for unit in units[:30]:
        state = "unknown"
        if systemctl:
            proc = subprocess.run(
                [systemctl, "is-active", unit],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=4,
                check=False,
            )
            state = proc.stdout.strip() or "inactive"
        out.append({"name": unit, "state": state})
    return out


def docker_status() -> dict:
    docker = shutil.which("docker")
    if not docker:
        return {"available": False, "containers": []}
    proc = subprocess.run(
        [docker, "ps", "--format", "{{json .}}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=7,
        check=False,
    )
    if proc.returncode != 0:
        return {
            "available": True,
            "error": proc.stderr.strip() or "docker non disponibile",
            "containers": [],
        }

    containers: list[dict] = []
    for line in proc.stdout.splitlines():
        try:
            item = json.loads(line)
            containers.append(
                {
                    "name": item.get("Names"),
                    "image": item.get("Image"),
                    "status": item.get("Status"),
                    "ports": item.get("Ports"),
                }
            )
        except json.JSONDecodeError:
            continue
    return {"available": True, "containers": containers}
