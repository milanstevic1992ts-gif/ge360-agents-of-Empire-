from __future__ import annotations

from pathlib import Path
import shlex

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

from .agents import create_agent, list_agents
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

CODEX_MODELS = [
    {
        "id": "gpt-5.6-luna",
        "name": "GPT-5.6 Luna",
        "profile": "Risparmio",
        "note": "Più economico per attività quotidiane e ad alto volume.",
    },
    {
        "id": "gpt-5.6-terra",
        "name": "GPT-5.6 Terra",
        "profile": "Bilanciato",
        "note": "Buon equilibrio tra capacità e consumo.",
    },
    {
        "id": "gpt-5.6-sol",
        "name": "GPT-5.6 Sol",
        "profile": "Massima qualità",
        "note": "Per debugging e lavori complessi; tende a consumare di più.",
    },
]
MODEL_IDS = {m["id"] for m in CODEX_MODELS}

app = FastAPI(
    title="GE360 Agent Control Center",
    version="0.2.0",
    docs_url=None,
    redoc_url=None,
)
app.mount("/assets", StaticFiles(directory=WEB), name="assets")


class NewSession(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    workspace_id: str
    model: str = "gpt-5.6-luna"


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class NewAgent(BaseModel):
    id: str = Field(min_length=2, max_length=40)
    description: str = Field(min_length=3, max_length=500)


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


def _command_for_model(model: str) -> str:
    if model not in MODEL_IDS:
        raise HTTPException(status_code=400, detail="Modello Codex non supportato dalla dashboard")
    parts = shlex.split(settings.codex_command)
    cleaned: list[str] = []
    skip_next = False
    for part in parts:
        if skip_next:
            skip_next = False
            continue
        if part in {"--model", "-m"}:
            skip_next = True
            continue
        if part.startswith("--model="):
            continue
        cleaned.append(part)
    cleaned.extend(["--model", model])
    return shlex.join(cleaned)


def _agents_payload():
    return [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "instructions": a.instructions,
            "status": "ready",
        }
        for a in list_agents()
    ]


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/status", dependencies=[Depends(guard)])
def status():
    sessions = [
        {
            "name": s.name,
            "created": s.created,
            "attached": s.attached,
            "model": s.model,
        }
        for s in tmux.list()
    ]
    return {
        "system": system_health(),
        "codex": codex_status(),
        "docker": docker_status(),
        "services": systemd_status(settings.systemd_units),
        "sessions": sessions,
        "agents": _agents_payload(),
        "models": CODEX_MODELS,
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
        "usage": {
            "source": "codex_status_command",
            "credit_balance_available": False,
            "note": "La CLI espone /status per uso token/quota della sessione. Il saldo crediti account completo non è esposto da una API CLI pubblica documentata.",
        },
    }


@app.get("/api/agents", dependencies=[Depends(guard)])
def agents():
    return {"agents": _agents_payload()}


@app.post("/api/agents", dependencies=[Depends(guard)])
def add_agent(body: NewAgent):
    try:
        profile = create_agent(body.id, body.description)
        return {
            "ok": True,
            "agent": {
                "id": profile.id,
                "name": profile.name,
                "description": profile.description,
                "instructions": profile.instructions,
                "status": "ready",
            },
            "note": "Apri una nuova sessione JARVIS/Codex per caricare il nuovo profilo.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/sessions", dependencies=[Depends(guard)])
def create_session(body: NewSession):
    ws = _workspace(body.workspace_id)
    command = _command_for_model(body.model)
    try:
        name = tmux.create(body.name, str(ws.path), command, model=body.model)
        return {"ok": True, "name": name, "model": body.model}
    except (TmuxError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sessions/{name}/screen", dependencies=[Depends(guard)])
def session_screen(name: str, lines: int = 180):
    try:
        return {"name": name, "screen": tmux.capture(name, lines)}
    except TmuxError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/sessions/{name}/usage", dependencies=[Depends(guard)])
def session_usage(name: str):
    try:
        screen = tmux.request_status(name)
        return {
            "name": name,
            "screen": screen,
            "note": "Output reale di /status. Può includere modello, token, contesto, limiti o reset quando Codex li espone.",
        }
    except TmuxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
