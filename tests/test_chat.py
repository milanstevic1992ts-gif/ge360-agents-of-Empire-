from pathlib import Path
import sqlite3
import tempfile
import unittest

import ge360_agent.chat as chat
from ge360_agent.appserver import CodexAppServer


SCHEMA = """
CREATE TABLE chat_threads (
    thread_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    cwd TEXT NOT NULL,
    model TEXT NOT NULL,
    effort TEXT NOT NULL,
    primary_agent TEXT NOT NULL,
    collaborators_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'idle',
    current_turn_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id TEXT NOT NULL,
    role TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'message',
    item_id TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'completed',
    meta_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE chat_server_requests (
    request_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    method TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'pending',
    result_json TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    resolved_at TEXT NOT NULL DEFAULT ''
);
"""


class ChatStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = chat.DB
        chat.DB = Path(self.tmp.name) / "chat.sqlite3"
        with sqlite3.connect(chat.DB) as conn:
            conn.executescript(SCHEMA)
        chat.create_thread(
            "thr_test",
            "Test chat",
            "ge360",
            "/tmp",
            "gpt-5.6-luna",
            "low",
            "ge360_developer",
            ["ge360_docker"],
        )

    def tearDown(self):
        chat.DB = self.old_db
        self.tmp.cleanup()

    def test_message_delta_is_persisted(self):
        chat.add_message("thr_test", "user", "ciao")
        chat.append_delta("thr_test", "item_1", "Ciao ")
        chat.append_delta("thr_test", "item_1", "Milan")
        rows = chat.list_messages("thr_test")
        self.assertEqual(rows[-1]["content"], "Ciao Milan")
        self.assertEqual(rows[-1]["status"], "in_progress")

    def test_appserver_notifications_build_chat(self):
        server = CodexAppServer()
        server._handle_notification(
            "turn/started",
            {"turn": {"id": "turn_1", "threadId": "thr_test"}},
        )
        server._handle_notification(
            "item/started",
            {
                "item": {
                    "id": "agent_1",
                    "type": "agentMessage",
                    "threadId": "thr_test",
                    "turnId": "turn_1",
                }
            },
        )
        server._handle_notification(
            "item/agentMessage/delta",
            {"itemId": "agent_1", "delta": "Sto controllando."},
        )
        server._handle_notification(
            "item/completed",
            {
                "item": {
                    "id": "agent_1",
                    "type": "agentMessage",
                    "threadId": "thr_test",
                    "turnId": "turn_1",
                    "text": "Controllo completato.",
                }
            },
        )
        rows = chat.list_messages("thr_test")
        assistant = [row for row in rows if row["role"] == "assistant"]
        self.assertEqual(len(assistant), 1)
        self.assertEqual(assistant[0]["content"], "Controllo completato.")
        self.assertEqual(assistant[0]["status"], "completed")

    def test_approval_becomes_visible_request(self):
        server = CodexAppServer()
        server._handle_server_request(
            {
                "id": 77,
                "method": "item/commandExecution/requestApproval",
                "params": {
                    "threadId": "thr_test",
                    "command": "systemctl restart demo",
                    "reason": "Serve riavviare il servizio",
                },
            }
        )
        req = chat.get_server_request("77")
        self.assertIsNotNone(req)
        self.assertEqual(req["status"], "pending")
        rows = chat.list_messages("thr_test")
        self.assertEqual(rows[-1]["kind"], "approval")
        self.assertEqual(rows[-1]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
