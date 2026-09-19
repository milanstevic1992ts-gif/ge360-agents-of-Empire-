from __future__ import annotations

from datetime import datetime
from pathlib import Path
import asyncio
import json
import queue
import re
import shlex

from fastapi import Depends, FastAPI, HTTPException, File, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

from . import chat
from .agents import create_agent, list_agents
from .appserver import AppServerError, app_server, probe_threads
from .activity import agents_for_session, latest_by_agent, record as record_activity, timeline as agent_timeline
from .codex import codex_status
from .config import Settings, load_settings
from .health import docker_status, system_health, systemd_status
from .security import auth_guard
from .smart import (
    activity as smart_activity,
    build_delegation_prompt,
    feedback as smart_feedback,
    list_recipes,
    remember_launch,
    route_task,
)
from .tmux import TmuxError, TmuxManager
from .uploads import attachment_context, list_files, resolve_files, save_upload
from .versioning import release_info, git_commit


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
        "note": "Costo minimo per attività quotidiane, diagnostica e lavori ad alto volume.",
    },
    {
        "id": "gpt-5.6-terra",
        "name": "GPT-5.6 Terra",
        "profile": "Bilanciato",
        "note": "Equilibrio tra intelligenza e consumo per lavori multi-step.",
    },
    {
        "id": "gpt-5.6-sol",
        "name": "GPT-5.6 Sol",
        "profile": "Massima qualità",
        "note": "Per debugging, architettura e problemi complessi; usa più risorse.",
    },
]
MODEL_IDS = {m["id"] for m in CODEX_MODELS}
REASONING_EFFORTS = [
    {"id": "none", "name": "Nessuno", "note": "Minimo consumo di ragionamento."},
    {"id": "low", "name": "Basso", "note": "Buono per diagnosi e modifiche semplici."},
    {"id": "medium", "name": "Medio", "note": "Bilanciato per la maggior parte dei lavori."},
    {"id": "high", "name": "Alto", "note": "Per debugging e pianificazione complessa."},
    {"id": "xhigh", "name": "Molto alto", "note": "Da usare solo quando serve davvero."},
    {"id": "max", "name": "Massimo", "note": "Massimo ragionamento e maggiore consumo."},
]
EFFORT_IDS = {e["id"] for e in REASONING_EFFORTS}

app = FastAPI(
    title="GE360 Agent Control Center",
    version=release_info().version,
    docs_url=None,
    redoc_url=None,
)
app.mount("/assets", StaticFiles(directory=WEB), name="assets")


@app.middleware("http")
async def no_stale_dashboard_cache(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/assets/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


class NewSession(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    workspace_id: str
    model: str = "gpt-5.6-luna"
    effort: str = "low"


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class NewAgent(BaseModel):
    id: str = Field(min_length=2, max_length=40)
    description: str = Field(min_length=3, max_length=500)


class SmartRouteRequest(BaseModel):
    task: str = Field(min_length=3, max_length=12000)
    attachments: list[str] = Field(default_factory=list)


class SmartLaunchRequest(BaseModel):
    task: str = Field(min_length=3, max_length=12000)
    workspace_id: str
    name: str = Field(default="", max_length=40)
    model: str = ""
    effort: str = ""
    attachments: list[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    session: str = Field(min_length=1, max_length=80)
    rating: int


class ChatThreadRequest(BaseModel):
    task: str = Field(min_length=1, max_length=20000)
    workspace_id: str
    attachments: list[str] = Field(default_factory=list)


class ChatMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    attachments: list[str] = Field(default_factory=list)


class ChatDecisionRequest(BaseModel):
    decision: str


class ChatAnswerRequest(BaseModel):
    answers: dict[str, list[str]]


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


def _command_for_model(model: str, effort: str) -> str:
    if model not in MODEL_IDS:
        raise HTTPException(status_code=400, detail="Modello Codex non supportato dalla dashboard")
    if effort not in EFFORT_IDS:
        raise HTTPException(status_code=400, detail="Livello di ragionamento non supportato")

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
    cleaned.extend(["--config", f'model_reasoning_effort="{effort}"'])
    return shlex.join(cleaned)


def _agents_payload():
    latest = latest_by_agent()
    payload = []
    for a in list_agents():
        event = latest.get(a.id, {})
        payload.append({
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "instructions": a.instructions,
            "status": event.get("status", "ready"),
            "last_event": event.get("event_type", ""),
            "last_detail": event.get("detail", ""),
            "last_seen": event.get("created_at", ""),
            "status_source": event.get("source", "ge360"),
        })
    return payload


def _route_text(task: str, files: list[dict]) -> str:
    if not files:
        return task
    names = ", ".join(item["original_name"] for item in files)
    return f"{task}\n\nALLEGATI: {names}"


def _chat_instructions(route) -> str:
    collaborators = ", ".join(route.collaborators) if route.collaborators else "nessuno"
    return (
        "Sei JARVIS, orchestratore GE360. Rispondi in modo naturale e conciso come in una chat, "
        "ma quando serve esegui realmente il lavoro usando strumenti e subagenti Codex. "
        f"Agente principale suggerito dal router: {route.primary_agent}. "
        f"Collaboratori suggeriti: {collaborators}. "
        f"Rischio stimato: {route.risk}. "
        "Mostra all'utente cosa stai facendo con messaggi utili, non con rumore da terminale. "
        "Quando un'operazione richiede approvazione, attendi la decisione dell'utente. "
        "Non inventare risultati, non memorizzare segreti e verifica sempre l'esito finale."
    )


def _chat_title(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:72] or "Nuova chat"


def _route_payload(route):
    return {
        "primary_agent": route.primary_agent,
        "collaborators": route.collaborators,
        "model": route.model,
        "risk": route.risk,
        "reason": route.reason,
        "matched": route.matched,
        "effort": (
            "low"
            if route.model == "gpt-5.6-luna"
            else ("medium" if route.model == "gpt-5.6-terra" else "high")
        ),
    }


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
    smart = smart_activity(12)
    release = release_info()
    return {
        "release": {"version": release.version, "schema_version": release.schema_version, "channel": release.channel, "commit": git_commit()},
        "system": system_health(),
        "codex": codex_status(),
        "docker": docker_status(),
        "services": systemd_status(settings.systemd_units),
        "sessions": sessions,
        "agents": _agents_payload(),
        "models": CODEX_MODELS,
        "reasoning_efforts": REASONING_EFFORTS,
        "recipes": list_recipes(),
        "smart": smart,
        "agent_timeline": agent_timeline(30),
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


@app.get("/api/codex/app-server/probe", dependencies=[Depends(guard)])
def codex_app_server_probe():
    return probe_threads()


@app.get("/api/chat/threads", dependencies=[Depends(guard)])
def chat_threads():
    return {"threads": chat.list_threads(60), "app_server": app_server.status()}


@app.get("/api/chat/threads/{thread_id}", dependencies=[Depends(guard)])
def chat_thread(thread_id: str):
    thread = chat.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Chat non trovata")
    return {"thread": thread, "messages": chat.list_messages(thread_id, 400)}


@app.post("/api/chat/threads", dependencies=[Depends(guard)])
def chat_create_thread(body: ChatThreadRequest):
    ws = _workspace(body.workspace_id)
    files = resolve_files(body.attachments)
    try:
        route = route_task(_route_text(body.task, files), _agents_payload())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    suggested = _route_payload(route)
    # Chat mode starts sandboxed. Codex can request an explicit approval card
    # when a task needs permissions outside the workspace.
    sandbox = "workspace-write"

    try:
        thread_id = app_server.create_thread(
            model=route.model,
            cwd=str(ws.path),
            developer_instructions=_chat_instructions(route),
            sandbox=sandbox,
        )
        thread = chat.create_thread(
            thread_id,
            _chat_title(body.task),
            ws.id,
            str(ws.path),
            route.model,
            suggested["effort"],
            route.primary_agent,
            route.collaborators,
        )
        user_message = chat.add_message(
            thread_id,
            "user",
            body.task,
            meta={"attachments": [f["original_name"] for f in files]},
        )
        record_activity(thread_id, "jarvis", "working", "chat_started", "Conversazione JARVIS avviata", "app-server")
        record_activity(thread_id, route.primary_agent, "working", "delegated", "Agente principale selezionato", "app-server")
        for collaborator in route.collaborators:
            record_activity(thread_id, collaborator, "waiting", "queued", "Collaboratore disponibile", "app-server")
        remember_launch(thread_id, _route_text(body.task, files), route)

        prompt = body.task
        file_context = attachment_context(files)
        if file_context:
            prompt += "\n\n" + file_context
        turn_id = app_server.start_turn(
            thread_id,
            prompt,
            effort=suggested["effort"],
            model=route.model,
        )
        return {
            "ok": True,
            "thread": chat.get_thread(thread_id) or thread,
            "user_message": user_message,
            "route": suggested,
            "turn_id": turn_id,
        }
    except AppServerError as exc:
        raise HTTPException(status_code=503, detail=f"Codex App Server: {exc}") from exc


@app.post("/api/chat/threads/{thread_id}/messages", dependencies=[Depends(guard)])
def chat_send_message(thread_id: str, body: ChatMessageRequest):
    thread = chat.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Chat non trovata")
    files = resolve_files(body.attachments)
    user_message = chat.add_message(
        thread_id,
        "user",
        body.text,
        meta={"attachments": [f["original_name"] for f in files]},
    )
    prompt = body.text
    file_context = attachment_context(files)
    if file_context:
        prompt += "\n\n" + file_context
    try:
        turn_id = app_server.start_turn(
            thread_id,
            prompt,
            effort=str(thread.get("effort") or "low"),
            model=str(thread.get("model") or ""),
        )
        record_activity(thread_id, "jarvis", "working", "chat_message", "Nuovo messaggio utente", "app-server")
        return {"ok": True, "message": user_message, "turn_id": turn_id}
    except AppServerError as exc:
        chat.add_message(thread_id, "system", str(exc), kind="error", status="error")
        raise HTTPException(status_code=503, detail=f"Codex App Server: {exc}") from exc


@app.get("/api/chat/threads/{thread_id}/messages", dependencies=[Depends(guard)])
def chat_messages(thread_id: str, limit: int = 400):
    if not chat.get_thread(thread_id):
        raise HTTPException(status_code=404, detail="Chat non trovata")
    return {"messages": chat.list_messages(thread_id, limit)}


@app.get("/api/chat/threads/{thread_id}/events", dependencies=[Depends(guard)])
async def chat_events(thread_id: str):
    if not chat.get_thread(thread_id):
        raise HTTPException(status_code=404, detail="Chat non trovata")
    box = app_server.subscribe(thread_id)

    async def stream():
        try:
            yield "event: ready\ndata: {}\n\n"
            while True:
                try:
                    event = await asyncio.to_thread(box.get, True, 15)
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"data: {payload}\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            app_server.unsubscribe(thread_id, box)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.post("/api/chat/threads/{thread_id}/interrupt", dependencies=[Depends(guard)])
def chat_interrupt(thread_id: str):
    if not chat.get_thread(thread_id):
        raise HTTPException(status_code=404, detail="Chat non trovata")
    try:
        app_server.interrupt(thread_id)
        return {"ok": True}
    except AppServerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/chat/requests/{request_id}/decision", dependencies=[Depends(guard)])
def chat_request_decision(request_id: str, body: ChatDecisionRequest):
    req = chat.get_server_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Richiesta Codex non trovata")
    if req.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Richiesta già risolta")
    if body.decision not in {"accept", "acceptForSession", "decline", "cancel"}:
        raise HTTPException(status_code=400, detail="Decisione non valida")
    method = str(req.get("method") or "")
    if method not in {
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
    }:
        raise HTTPException(status_code=400, detail="Questa richiesta non usa una decisione semplice")
    try:
        app_server.respond_server_request(request_id, {"decision": body.decision})
        return {"ok": True}
    except AppServerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/chat/requests/{request_id}/answer", dependencies=[Depends(guard)])
def chat_request_answer(request_id: str, body: ChatAnswerRequest):
    req = chat.get_server_request(request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Richiesta Codex non trovata")
    if req.get("status") != "pending":
        raise HTTPException(status_code=409, detail="Richiesta già risolta")
    if req.get("method") != "item/tool/requestUserInput":
        raise HTTPException(status_code=400, detail="La richiesta non accetta risposte testuali")
    answers = {key: {"answers": values} for key, values in body.answers.items()}
    try:
        app_server.respond_server_request(request_id, {"answers": answers})
        return {"ok": True}
    except AppServerError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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


@app.get("/api/files", dependencies=[Depends(guard)])
def files_index(limit: int = 100):
    return {"files": list_files(limit)}


@app.post("/api/files", dependencies=[Depends(guard)])
async def files_upload(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Nessun file ricevuto")
    saved = []
    try:
        for upload in files[:20]:
            saved.append(await save_upload(upload))
        return {"ok": True, "files": saved}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/smart/route", dependencies=[Depends(guard)])
def smart_route(body: SmartRouteRequest):
    files = resolve_files(body.attachments)
    try:
        route = route_task(_route_text(body.task, files), _agents_payload())
        return {"ok": True, "route": _route_payload(route), "attachments": files}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/smart/launch", dependencies=[Depends(guard)])
def smart_launch(body: SmartLaunchRequest):
    ws = _workspace(body.workspace_id)
    files = resolve_files(body.attachments)
    try:
        route = route_task(_route_text(body.task, files), _agents_payload())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    suggested = _route_payload(route)
    model = body.model or suggested["model"]
    effort = body.effort or suggested["effort"]
    command = _command_for_model(model, effort)

    raw_name = body.name.strip() or f"smart-{datetime.now().strftime('%H%M%S')}"
    try:
        name = tmux.create(raw_name, str(ws.path), command, model=model)
        record_activity(name, "jarvis", "working", "session_started", "Smart task avviato", "ge360")
        record_activity(name, route.primary_agent, "working", "delegated", "Agente principale selezionato dal router", "ge360")
        for collaborator in route.collaborators:
            record_activity(name, collaborator, "waiting", "queued", "Collaboratore pronto se richiesto", "ge360")
        prompt = build_delegation_prompt(body.task, route)
        file_context = attachment_context(files)
        if file_context:
            prompt = prompt + "\n\n" + file_context
        tmux.send(name, prompt)
        event_id = remember_launch(name, _route_text(body.task, files), route)
        return {
            "ok": True,
            "name": name,
            "model": model,
            "effort": effort,
            "event_id": event_id,
            "route": suggested,
            "attachments": files,
        }
    except (TmuxError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/smart/feedback", dependencies=[Depends(guard)])
def smart_feedback_endpoint(body: FeedbackRequest):
    try:
        updated = smart_feedback(body.session, body.rating)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Nessun incarico smart trovato per questa sessione")
    return {"ok": True}


@app.get("/api/smart/activity", dependencies=[Depends(guard)])
def smart_activity_endpoint(limit: int = 20):
    return smart_activity(limit)


@app.get("/api/agents/timeline", dependencies=[Depends(guard)])
def agents_timeline(limit: int = 80, session: str = ""):
    return {"events": agent_timeline(limit, session)}


@app.post("/api/sessions", dependencies=[Depends(guard)])
def create_session(body: NewSession):
    ws = _workspace(body.workspace_id)
    command = _command_for_model(body.model, body.effort)
    try:
        name = tmux.create(body.name, str(ws.path), command, model=body.model)
        record_activity(name, "jarvis", "working", "session_started", "Sessione manuale avviata", "ge360")
        return {"ok": True, "name": name, "model": body.model, "effort": body.effort}
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
        record_activity(name, "jarvis", "working", "message_sent", "Nuovo input ricevuto", "ge360")
        return {"ok": True}
    except TmuxError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/sessions/{name}", dependencies=[Depends(guard)])
def stop_session(name: str):
    try:
        involved = agents_for_session(name)
        tmux.stop(name)
        for agent_id in involved:
            record_activity(name, agent_id, "done", "session_stopped", "Sessione chiusa", "ge360")
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
