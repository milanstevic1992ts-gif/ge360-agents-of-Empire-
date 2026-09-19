from __future__ import annotations

import json
import queue
import shutil
import subprocess
import threading
import time
from typing import Any

from . import chat


class AppServerError(RuntimeError):
    pass


def _command_text(command: Any) -> str:
    if isinstance(command, list):
        return " ".join(str(x) for x in command)
    if isinstance(command, str):
        return command
    if isinstance(command, dict):
        for key in ("command", "argv", "cmd"):
            value = command.get(key)
            if isinstance(value, list):
                return " ".join(str(x) for x in value)
            if isinstance(value, str):
                return value
    return ""


def _item_text(item: dict) -> str:
    for key in ("text", "message", "summary", "review", "query"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                value = part.get("text") or part.get("content")
                if isinstance(value, str):
                    parts.append(value)
        return "\n".join(parts)
    return ""


class CodexAppServer:
    def __init__(self) -> None:
        self._proc: subprocess.Popen[str] | None = None
        self._start_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._pending: dict[int, queue.Queue] = {}
        self._next_id = 100
        self._ready = False
        self._loaded_threads: set[str] = set()
        self._turn_threads: dict[str, str] = {}
        self._item_threads: dict[str, str] = {}
        self._server_request_ids: dict[str, Any] = {}
        self._subscribers_lock = threading.Lock()
        self._subscribers: dict[str, list[queue.Queue]] = {}
        self._last_error = ""

    def available(self) -> bool:
        return bool(shutil.which("codex"))

    def status(self) -> dict:
        running = bool(self._proc and self._proc.poll() is None and self._ready)
        return {
            "available": self.available(),
            "running": running,
            "transport": "stdio",
            "last_error": self._last_error[-1000:],
        }

    def start(self) -> None:
        with self._start_lock:
            if self._proc and self._proc.poll() is None and self._ready:
                return
            codex = shutil.which("codex")
            if not codex:
                raise AppServerError("Codex CLI non trovato")

            self._ready = False
            self._loaded_threads.clear()
            self._turn_threads.clear()
            self._item_threads.clear()
            self._proc = subprocess.Popen(
                [codex, "app-server", "--listen", "stdio://"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            if not self._proc.stdin or not self._proc.stdout:
                raise AppServerError("Impossibile aprire stdio di Codex App Server")

            threading.Thread(target=self._reader_loop, daemon=True, name="ge360-codex-reader").start()
            if self._proc.stderr:
                threading.Thread(target=self._stderr_loop, daemon=True, name="ge360-codex-stderr").start()

            result = self._request_started(
                "initialize",
                {
                    "clientInfo": {
                        "name": "ge360_jarvis",
                        "title": "GE360 JARVIS",
                        "version": "0.7.0",
                    }
                },
                timeout=8,
            )
            if not isinstance(result, dict):
                raise AppServerError("Handshake Codex App Server non valido")
            self._send({"method": "initialized", "params": {}})
            self._ready = True
            self._last_error = ""

    def stop(self) -> None:
        proc = self._proc
        self._ready = False
        if not proc:
            return
        try:
            proc.terminate()
            proc.wait(timeout=1)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _stderr_loop(self) -> None:
        proc = self._proc
        if not proc or not proc.stderr:
            return
        for line in proc.stderr:
            line = line.strip()
            if line:
                self._last_error = line

    def _reader_loop(self) -> None:
        proc = self._proc
        if not proc or not proc.stdout:
            return
        try:
            for line in proc.stdout:
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._handle_message(message)
        finally:
            self._ready = False
            error = self._last_error or "Codex App Server terminato"
            with self._pending_lock:
                pending = list(self._pending.values())
                self._pending.clear()
            for box in pending:
                try:
                    box.put_nowait({"error": {"message": error}})
                except queue.Full:
                    pass

    def _send(self, message: dict) -> None:
        proc = self._proc
        if not proc or proc.poll() is not None or not proc.stdin:
            raise AppServerError(self._last_error or "Codex App Server non attivo")
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        with self._write_lock:
            proc.stdin.write(payload + "\n")
            proc.stdin.flush()

    def _new_id(self) -> int:
        with self._pending_lock:
            self._next_id += 1
            return self._next_id

    def _request_started(self, method: str, params: dict | None = None, timeout: float = 20) -> Any:
        request_id = self._new_id()
        box: queue.Queue = queue.Queue(maxsize=1)
        with self._pending_lock:
            self._pending[request_id] = box
        try:
            self._send({"method": method, "id": request_id, "params": params or {}})
            response = box.get(timeout=timeout)
        except queue.Empty as exc:
            raise AppServerError(f"Timeout Codex App Server: {method}") from exc
        finally:
            with self._pending_lock:
                self._pending.pop(request_id, None)

        if "error" in response:
            error = response.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise AppServerError(message or f"Errore App Server: {method}")
        return response.get("result")

    def request(self, method: str, params: dict | None = None, timeout: float = 20) -> Any:
        self.start()
        return self._request_started(method, params, timeout)

    def _handle_message(self, message: dict) -> None:
        if "id" in message and "method" not in message:
            request_id = message.get("id")
            if isinstance(request_id, int):
                with self._pending_lock:
                    box = self._pending.get(request_id)
                if box:
                    try:
                        box.put_nowait(message)
                    except queue.Full:
                        pass
            return

        if "id" in message and "method" in message:
            self._handle_server_request(message)
            return

        method = message.get("method")
        params = message.get("params") or {}
        if isinstance(method, str):
            self._handle_notification(method, params if isinstance(params, dict) else {})

    def _thread_for(self, params: dict, item_id: str = "", turn_id: str = "") -> str:
        direct = params.get("threadId")
        if isinstance(direct, str) and direct:
            return direct
        item = params.get("item")
        if isinstance(item, dict):
            value = item.get("threadId")
            if isinstance(value, str) and value:
                return value
            if not turn_id:
                value = item.get("turnId")
                if isinstance(value, str):
                    turn_id = value
        turn = params.get("turn")
        if isinstance(turn, dict):
            value = turn.get("threadId")
            if isinstance(value, str) and value:
                return value
            if not turn_id:
                value = turn.get("id")
                if isinstance(value, str):
                    turn_id = value
        if item_id and item_id in self._item_threads:
            return self._item_threads[item_id]
        if turn_id and turn_id in self._turn_threads:
            return self._turn_threads[turn_id]
        return ""

    def _emit(self, thread_id: str, event: dict) -> None:
        if not thread_id:
            return
        event = {"thread_id": thread_id, "at": time.time(), **event}
        with self._subscribers_lock:
            targets = list(self._subscribers.get(thread_id, []))
        for box in targets:
            try:
                box.put_nowait(event)
            except queue.Full:
                try:
                    box.get_nowait()
                    box.put_nowait(event)
                except Exception:
                    pass

    def subscribe(self, thread_id: str) -> queue.Queue:
        box: queue.Queue = queue.Queue(maxsize=500)
        with self._subscribers_lock:
            self._subscribers.setdefault(thread_id, []).append(box)
        return box

    def unsubscribe(self, thread_id: str, box: queue.Queue) -> None:
        with self._subscribers_lock:
            items = self._subscribers.get(thread_id, [])
            if box in items:
                items.remove(box)
            if not items:
                self._subscribers.pop(thread_id, None)

    def _handle_server_request(self, message: dict) -> None:
        method = str(message.get("method") or "")
        original_id = message.get("id")
        request_key = str(original_id)
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        thread_id = self._thread_for(params)
        if not thread_id:
            value = params.get("threadId")
            thread_id = value if isinstance(value, str) else ""

        self._server_request_ids[request_key] = original_id
        chat.create_server_request(request_key, thread_id, method, params)

        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
            "item/permissions/requestApproval",
        }:
            command = _command_text(params.get("command"))
            reason = str(params.get("reason") or "")
            title = command or reason or "Operazione richiesta da Codex"
            row = chat.add_message(
                thread_id,
                "tool",
                title,
                kind="approval",
                item_id=f"request:{request_key}",
                status="pending",
                meta={
                    "request_id": request_key,
                    "method": method,
                    "params": params,
                },
            )
            chat.update_thread(thread_id, status="waiting")
            self._emit(thread_id, {"type": "message.upsert", "message": row})
            self._emit(thread_id, {"type": "thread.status", "status": "waiting"})
            return

        if method == "item/tool/requestUserInput":
            questions = params.get("questions") if isinstance(params.get("questions"), list) else []
            summary = "\n".join(
                str(q.get("question") or q.get("header") or "Input richiesto")
                for q in questions
                if isinstance(q, dict)
            )
            row = chat.add_message(
                thread_id,
                "tool",
                summary or "Codex richiede una risposta.",
                kind="input_request",
                item_id=f"request:{request_key}",
                status="pending",
                meta={
                    "request_id": request_key,
                    "method": method,
                    "questions": questions,
                },
            )
            chat.update_thread(thread_id, status="waiting")
            self._emit(thread_id, {"type": "message.upsert", "message": row})
            self._emit(thread_id, {"type": "thread.status", "status": "waiting"})
            return

        row = chat.add_message(
            thread_id,
            "tool",
            f"Richiesta Codex: {method}",
            kind="request",
            item_id=f"request:{request_key}",
            status="pending",
            meta={"request_id": request_key, "method": method, "params": params},
        )
        self._emit(thread_id, {"type": "message.upsert", "message": row})

    def _handle_notification(self, method: str, params: dict) -> None:
        if method == "thread/started":
            thread = params.get("thread") if isinstance(params.get("thread"), dict) else {}
            thread_id = str(thread.get("id") or "")
            if thread_id:
                self._loaded_threads.add(thread_id)
            return

        if method == "thread/status/changed":
            thread_id = str(params.get("threadId") or "")
            status_obj = params.get("status") if isinstance(params.get("status"), dict) else {}
            kind = str(status_obj.get("type") or "idle")
            status = "working" if kind == "active" else ("error" if kind == "systemError" else "idle")
            if thread_id:
                chat.update_thread(thread_id, status=status)
                self._emit(thread_id, {"type": "thread.status", "status": status, "raw": status_obj})
            return

        if method == "turn/started":
            turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
            thread_id = str(turn.get("threadId") or "")
            turn_id = str(turn.get("id") or "")
            if thread_id and turn_id:
                self._turn_threads[turn_id] = thread_id
                chat.update_thread(thread_id, status="working", turn_id=turn_id)
                self._emit(thread_id, {"type": "thread.status", "status": "working", "turn_id": turn_id})
            return

        if method == "turn/completed":
            turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
            thread_id = str(turn.get("threadId") or "")
            turn_id = str(turn.get("id") or "")
            final = str(turn.get("status") or "completed")
            status = "error" if final == "failed" else "idle"
            if thread_id:
                chat.update_thread(thread_id, status=status, turn_id="")
                self._emit(
                    thread_id,
                    {
                        "type": "turn.completed",
                        "status": final,
                        "turn_id": turn_id,
                        "error": (turn.get("error") or {}),
                    },
                )
                self._emit(thread_id, {"type": "thread.status", "status": status})
            if turn_id:
                self._turn_threads.pop(turn_id, None)
            return

        if method == "item/agentMessage/delta":
            item_id = str(params.get("itemId") or "")
            thread_id = self._thread_for(params, item_id=item_id)
            delta = str(params.get("delta") or params.get("textDelta") or params.get("text") or "")
            if thread_id and item_id and delta:
                row = chat.append_delta(thread_id, item_id, delta)
                self._emit(thread_id, {"type": "message.upsert", "message": row})
            return

        if method == "item/reasoning/summaryTextDelta":
            item_id = str(params.get("itemId") or "")
            thread_id = self._thread_for(params, item_id=item_id)
            delta = str(params.get("delta") or params.get("textDelta") or "")
            if thread_id and item_id and delta:
                row = chat.append_delta(thread_id, item_id, delta, role="assistant", kind="reasoning")
                self._emit(thread_id, {"type": "message.upsert", "message": row})
            return

        if method == "item/commandExecution/outputDelta":
            item_id = str(params.get("itemId") or "")
            thread_id = self._thread_for(params, item_id=item_id)
            delta = str(params.get("delta") or "")
            if thread_id and item_id and delta:
                existing = chat.find_by_item(thread_id, item_id)
                prefix = "" if existing and existing.get("content") else ""
                row = chat.append_delta(thread_id, item_id, prefix + delta, role="tool", kind="tool")
                self._emit(thread_id, {"type": "message.upsert", "message": row})
            return

        if method in {"item/started", "item/completed"}:
            item = params.get("item") if isinstance(params.get("item"), dict) else {}
            item_id = str(item.get("id") or "")
            item_type = str(item.get("type") or "")
            turn_id = str(item.get("turnId") or params.get("turnId") or "")
            thread_id = self._thread_for(params, item_id=item_id, turn_id=turn_id)
            if turn_id and thread_id:
                self._turn_threads[turn_id] = thread_id
            if item_id and thread_id:
                self._item_threads[item_id] = thread_id
            if not thread_id or not item_id:
                return

            done = method == "item/completed"
            state = "completed" if done else "in_progress"

            if item_type == "userMessage":
                return
            if item_type == "agentMessage":
                text = _item_text(item)
                if text:
                    row = chat.upsert_item(
                        thread_id,
                        item_id,
                        role="assistant",
                        kind="message",
                        content=text,
                        status=state,
                        meta={"item_type": item_type},
                    )
                else:
                    existing = chat.find_by_item(thread_id, item_id)
                    row = chat.update_item_status(thread_id, item_id, state) if existing else {}
                if row:
                    self._emit(thread_id, {"type": "message.upsert", "message": row})
                return
            if item_type == "reasoning":
                text = _item_text(item)
                if text:
                    row = chat.upsert_item(
                        thread_id,
                        item_id,
                        role="assistant",
                        kind="reasoning",
                        content=text,
                        status=state,
                        meta={"item_type": item_type},
                    )
                    self._emit(thread_id, {"type": "message.upsert", "message": row})
                return

            if item_type == "commandExecution":
                command = _command_text(item.get("command"))
                content = command or "Comando"
                output = item.get("aggregatedOutput") or item.get("output")
                if isinstance(output, str) and output:
                    content += "\n\n" + output
                row = chat.upsert_item(
                    thread_id,
                    item_id,
                    role="tool",
                    kind="tool",
                    content=content,
                    status=str(item.get("status") or state),
                    meta={"item_type": item_type, "cwd": item.get("cwd")},
                )
                self._emit(thread_id, {"type": "message.upsert", "message": row})
                return

            if item_type in {"fileChange", "mcpToolCall", "webSearch", "plan", "contextCompaction"}:
                label = {
                    "fileChange": "Modifica file",
                    "mcpToolCall": str(item.get("tool") or "MCP tool"),
                    "webSearch": str(item.get("query") or "Ricerca web"),
                    "plan": "Piano",
                    "contextCompaction": "Compattazione contesto",
                }.get(item_type, item_type)
                text = _item_text(item)
                row = chat.upsert_item(
                    thread_id,
                    item_id,
                    role="tool" if item_type != "plan" else "assistant",
                    kind="tool" if item_type != "plan" else "plan",
                    content=(label + ("\n\n" + text if text and text != label else "")),
                    status=str(item.get("status") or state),
                    meta={"item_type": item_type},
                )
                self._emit(thread_id, {"type": "message.upsert", "message": row})
                return

    def create_thread(
        self,
        *,
        model: str,
        cwd: str,
        developer_instructions: str,
        sandbox: str = "workspace-write",
    ) -> str:
        result = self.request(
            "thread/start",
            {
                "model": model,
                "cwd": cwd,
                "approvalPolicy": "on-request",
                "approvalsReviewer": "user",
                "sandbox": sandbox,
                "developerInstructions": developer_instructions,
                "serviceName": "ge360_jarvis",
            },
            timeout=30,
        )
        thread = result.get("thread") if isinstance(result, dict) else {}
        thread_id = str(thread.get("id") or "") if isinstance(thread, dict) else ""
        if not thread_id:
            raise AppServerError("Codex non ha restituito threadId")
        self._loaded_threads.add(thread_id)
        return thread_id

    def ensure_thread(self, thread_id: str) -> None:
        self.start()
        if thread_id in self._loaded_threads:
            return
        self._request_started("thread/resume", {"threadId": thread_id}, timeout=30)
        self._loaded_threads.add(thread_id)

    def start_turn(
        self,
        thread_id: str,
        text: str,
        *,
        effort: str | None = None,
        model: str | None = None,
    ) -> str:
        self.ensure_thread(thread_id)
        thread = chat.get_thread(thread_id) or {}
        current_turn = str(thread.get("current_turn_id") or "")
        if thread.get("status") in {"working", "waiting"} and current_turn:
            result = self.request(
                "turn/steer",
                {
                    "threadId": thread_id,
                    "input": [{"type": "text", "text": text}],
                    "expectedTurnId": current_turn,
                },
                timeout=20,
            )
            return str((result or {}).get("turnId") or current_turn)

        params: dict[str, Any] = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": text}],
        }
        if effort:
            params["effort"] = effort
        if model:
            params["model"] = model
        result = self.request("turn/start", params, timeout=30)
        turn = result.get("turn") if isinstance(result, dict) else {}
        turn_id = str(turn.get("id") or "") if isinstance(turn, dict) else ""
        if turn_id:
            self._turn_threads[turn_id] = thread_id
            chat.update_thread(thread_id, status="working", turn_id=turn_id)
        return turn_id

    def interrupt(self, thread_id: str) -> None:
        thread = chat.get_thread(thread_id) or {}
        turn_id = str(thread.get("current_turn_id") or "")
        if not turn_id:
            return
        self.request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id}, timeout=15)

    def respond_server_request(self, request_id: str, result: dict) -> None:
        original_id = self._server_request_ids.get(request_id, request_id)
        self._send({"id": original_id, "result": result})
        req = chat.get_server_request(request_id) or {}
        chat.resolve_server_request(request_id, result)
        thread_id = str(req.get("thread_id") or "")
        if thread_id:
            row = chat.find_by_item(thread_id, f"request:{request_id}")
            if row:
                updated = chat.update_item_status(thread_id, f"request:{request_id}", "resolved")
                self._emit(thread_id, {"type": "message.upsert", "message": updated})
            chat.update_thread(thread_id, status="working")
            self._emit(thread_id, {"type": "thread.status", "status": "working"})


app_server = CodexAppServer()


def probe_threads(timeout: float = 2.5) -> dict:
    if not app_server.available():
        return {"available": False, "reason": "codex_not_found", "threads": []}
    try:
        result = app_server.request(
            "thread/list",
            {
                "cursor": None,
                "limit": 30,
                "sortKey": "updated_at",
                "sourceKinds": [
                    "cli",
                    "appServer",
                    "subAgent",
                    "subAgentThreadSpawn",
                    "subAgentOther",
                ],
            },
            timeout=max(2.5, timeout),
        )
        result = result or {}
        return {
            "available": True,
            "running": True,
            "protocol": "stdio",
            "threads": result.get("data") or [],
            "next_cursor": result.get("nextCursor"),
        }
    except Exception as exc:
        return {
            "available": True,
            "running": False,
            "reason": str(exc),
            "threads": [],
        }
