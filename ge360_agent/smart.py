from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
import tomllib


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
RECIPES = ROOT / "recipes"

KNOWN_AGENTS = {
    "ge360_sysadmin": {
        "keywords": {
            "debian", "systemd", "servizio", "service", "rete", "network", "permessi",
            "permission", "apt", "pacchetto", "package", "disco", "ram", "cpu", "tailscale",
            "firewall", "ssh", "linux", "host", "server",
        },
        "label": "SysAdmin",
    },
    "ge360_docker": {
        "keywords": {
            "docker", "compose", "container", "volume", "healthcheck", "image", "registry",
            "network", "stack", "worker", "scheduler", "mariadb", "mysql", "redis",
        },
        "label": "Docker",
    },
    "ge360_developer": {
        "keywords": {
            "codice", "code", "bug", "python", "javascript", "typescript", "api", "fastapi",
            "git", "github", "repo", "repository", "test", "refactor", "patch", "frontend",
            "backend", "apk", "android", "build",
        },
        "label": "Developer",
    },
    "ge360_crm": {
        "keywords": {
            "suitecrm", "mautic", "prospex", "crm", "campagna", "campaign", "contatti",
            "contacts", "lead", "email", "marketing", "scheduler", "inbound", "mailbox",
        },
        "label": "CRM",
    },
    "ge360_automation": {
        "keywords": {
            "n8n", "workflow", "webhook", "automazione", "automation", "trigger", "integrazione",
            "integration", "retry", "flow", "cron", "orchestrazione", "orchestration",
        },
        "label": "Automation",
    },
    "ge360_wordpress_seo": {
        "keywords": {
            "wordpress", "wp", "plugin", "tema", "theme", "seo", "google business", "schema",
            "pagina", "page", "sito", "website", "triesteincostruzione", "performance",
            "core web vitals",
        },
        "label": "WordPress/SEO",
    },
}

HIGH_RISK = {
    "delete", "cancella", "elimina", "remove", "rm ", "drop ", "truncate", "volume rm",
    "prune", "force push", "reset database", "reset db", "firewall", "ssh", "password",
    "token", "secret", "credential", "credenzial", "pubblico", "public internet",
}
COMPLEX = {
    "architettura", "architecture", "migrazione", "migration", "corruzione", "corrupted",
    "sicurezza", "security", "race condition", "refactor", "multi-agent", "multi agent",
    "database", "schema", "concorrenza", "concurrency",
}

_SECRET_PATTERNS = [
    re.compile(r"(?i)(password|passwd|token|api[_ -]?key|secret)\s*[:=]\s*\S+"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
]


@dataclass(frozen=True)
class Route:
    primary_agent: str
    collaborators: list[str]
    model: str
    risk: str
    reason: str
    matched: dict[str, int]


def _tokens(text: str) -> str:
    return " " + re.sub(r"\s+", " ", text.lower()).strip() + " "


def _score_agent(text: str, agent_id: str, description: str = "") -> int:
    haystack = _tokens(text)
    config = KNOWN_AGENTS.get(agent_id)
    score = 0
    if config:
        for keyword in config["keywords"]:
            if keyword in haystack:
                score += 3 if " " in keyword else 2

    for word in re.findall(r"[a-z0-9_-]{4,}", description.lower()):
        if word in haystack:
            score += 1
    return score


def route_task(task: str, agents: list[dict]) -> Route:
    clean = task.strip()
    if not clean:
        raise ValueError("Descrivi prima il lavoro da eseguire")

    scores: dict[str, int] = {}
    for agent in agents:
        agent_id = str(agent.get("id", ""))
        if not agent_id:
            continue
        scores[agent_id] = _score_agent(clean, agent_id, str(agent.get("description", "")))

    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    primary = ranked[0][0] if ranked and ranked[0][1] > 0 else "ge360_developer"

    collaborators = [
        agent_id
        for agent_id, score in ranked[1:4]
        if score > 0 and score >= max(2, ranked[0][1] // 2 if ranked else 2)
    ]

    lower = clean.lower()
    risk_hits = [word for word in HIGH_RISK if word in lower]
    risk = "high" if len(risk_hits) >= 2 else ("medium" if risk_hits else "low")

    domain_count = sum(1 for _, score in ranked if score > 0)
    complex_hits = [word for word in COMPLEX if word in lower]
    if complex_hits and (domain_count >= 2 or len(clean) > 500):
        model = "gpt-5.6-sol"
    elif domain_count >= 2 or complex_hits or len(clean) > 350:
        model = "gpt-5.6-terra"
    else:
        model = "gpt-5.6-luna"

    label = KNOWN_AGENTS.get(primary, {}).get("label", primary)
    reason_bits = [f"{label} è il profilo con più segnali pertinenti"]
    if collaborators:
        reason_bits.append("il lavoro tocca più domini, quindi conviene una delega mirata")
    if risk != "low":
        reason_bits.append(f"rilevati indicatori di rischio {risk}")
    if model == "gpt-5.6-luna":
        reason_bits.append("Luna è sufficiente e riduce il consumo")
    elif model == "gpt-5.6-terra":
        reason_bits.append("Terra bilancia complessità e consumo")
    else:
        reason_bits.append("Sol è riservato a questo caso perché la complessità è elevata")

    return Route(
        primary_agent=primary,
        collaborators=collaborators,
        model=model,
        risk=risk,
        reason="; ".join(reason_bits) + ".",
        matched={agent: score for agent, score in ranked if score > 0},
    )


def list_recipes() -> list[dict]:
    result: list[dict] = []
    if not RECIPES.exists():
        return result
    for path in sorted(RECIPES.glob("*.toml")):
        try:
            with path.open("rb") as fh:
                data = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        result.append(
            {
                "id": path.stem,
                "name": str(data.get("name", path.stem)),
                "description": str(data.get("description", "")),
                "agent": str(data.get("agent", "")),
                "model": str(data.get("model", "gpt-5.6-luna")),
                "risk": str(data.get("risk", "low")),
                "prompt": str(data.get("prompt", "")),
            }
        )
    return result


def _db() -> sqlite3.Connection:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(RUNTIME / "jarvis-smart.sqlite3")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS task_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            session TEXT NOT NULL,
            task_preview TEXT NOT NULL,
            primary_agent TEXT NOT NULL,
            collaborators TEXT NOT NULL,
            model TEXT NOT NULL,
            risk TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'launched',
            rating INTEGER
        )
        """
    )
    conn.commit()
    return conn


def safe_preview(task: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", task).strip()
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda m: m.group(1) + "=[REDACTED]" if m.lastindex else "[REDACTED]", text)
    return text[:limit]


def remember_launch(session: str, task: str, route: Route) -> int:
    with _db() as conn:
        cur = conn.execute(
            """
            INSERT INTO task_events
            (created_at, session, task_preview, primary_agent, collaborators, model, risk)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                session,
                safe_preview(task),
                route.primary_agent,
                ",".join(route.collaborators),
                route.model,
                route.risk,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def feedback(session: str, rating: int) -> bool:
    if rating not in (-1, 1):
        raise ValueError("Feedback non valido")
    with _db() as conn:
        row = conn.execute(
            "SELECT id FROM task_events WHERE session=? ORDER BY id DESC LIMIT 1",
            (session,),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "UPDATE task_events SET rating=?, status=? WHERE id=?",
            (rating, "success" if rating > 0 else "needs_improvement", int(row["id"])),
        )
        conn.commit()
        return True


def activity(limit: int = 20) -> dict:
    limit = max(1, min(limit, 100))
    with _db() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, session, task_preview, primary_agent, collaborators,
                   model, risk, status, rating
            FROM task_events ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        stats = conn.execute(
            """
            SELECT primary_agent,
                   COUNT(*) AS total,
                   SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END) AS good,
                   SUM(CASE WHEN rating=-1 THEN 1 ELSE 0 END) AS bad
            FROM task_events
            GROUP BY primary_agent
            ORDER BY total DESC
            """
        ).fetchall()

    return {
        "events": [dict(row) for row in rows],
        "stats": [dict(row) for row in stats],
    }


def build_delegation_prompt(task: str, route: Route) -> str:
    collaborators = ", ".join(route.collaborators) if route.collaborators else "nessuno"
    return (
        "JARVIS SMART ROUTER ha preparato questo incarico. "
        f"Agente principale consigliato: {route.primary_agent}. "
        f"Collaboratori consigliati: {collaborators}. "
        f"Livello di rischio: {route.risk}. "
        "Usa i subagenti nativi Codex quando utile, mantieni tu la responsabilità del risultato finale, "
        "segui i gate di sicurezza GE360 e verifica il risultato. "
        "Non memorizzare password, token o segreti.\\n\\n"
        f"INCARICO UTENTE:\\n{task.strip()}"
    )
