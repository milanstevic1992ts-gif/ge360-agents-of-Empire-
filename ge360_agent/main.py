from __future__ import annotations

from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

from .codex import codex_status
from .config import Settings, load_settings
from .health import docker_status, system_health, systemd_status
from .security import auth_guard
from .tmux import TmuxError, TmuxManager


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
settings: Settings = load_settings()
tmux = TmuxManager(settings.session_prefix)
guard = auth_guard(settings.token)

app = FastAPI(
    title="GE360 Agent Control Center",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
)
app.mount("/assets", StaticFiles(directory=WEB), name="assets")


class NewSession(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    workspace_id: str


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


def _workspace(workspace_id: str):
    for ws in settings.workspaces:
        if ws.id == workspace_id:
            if not ws.path.exists():
                raise HTTPException(
                    status_code=409,
                    detail=f"Workspace non trovato sul server: {ws.path}",
                )
            return ws
    raise HTTPException(status_code=404, detail="Workspace non configurato")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/status", dependencies=[Depends(guard)])
def status():
    sessions = [
        {"name": s.name, "created": s.created, "attached": s.attached}
        for s in tmux.list()
    ]
    return {
        "system": system_health(),
        "codex": codex_status(),
        "docker": docker_status(),
        "services": systemd_status(settings.systemd_units),
        "sessions": sessions,
        "workspaces": [
            {
                "id": ws.id,
                "name": ws.name,
                "path": str(ws.path),
                "exists": ws.path.exists(),
            }
            for ws in settings.workspaces
        ],
        "security": {
            "token_required": bool(settings.token),
            "bind": settings.host,
        },
    }


@app.post("/api/sessions", dependencies=[Depends(guard)])
def create_session(body: NewSession):
    ws = _workspace(body.workspace_id)
    try:
        name = tmux.create(body.name, str(ws.path), settings.codex_command)
        return {"ok": True, "name": name}
    except (TmuxError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sessions/{name}/screen", dependencies=[Depends(guard)])
def session_screen(name: str, lines: int = 180):
    try:
        return {"name": name, "screen": tmux.capture(name, lines)}
    except TmuxError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/sessions/{name}/message", dependencies=[Depends(guard)])
def session_message(name: str, body: Message):
    try:
        tmux.send(name, body.text)
        return {"ok": True}
    except TmuxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/sessions/{name}", dependencies=[Depends(guard)])
def stop_session(name: str):
    try:
        tmux.stop(name)
        return {"ok": True}
    except TmuxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def run() -> None:
    uvicorn.run(
        "ge360_agent.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        workers=1,
    )


if __name__ == "__main__":
    run()
