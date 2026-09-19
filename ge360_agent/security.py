from __future__ import annotations

import hmac
import re
from fastapi import Header, HTTPException

_SESSION_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,39}$")


def validate_session_name(name: str) -> str:
    if not _SESSION_RE.fullmatch(name):
        raise ValueError(
            "Nome sessione non valido: usa 1-40 caratteri tra lettere, numeri, _ e -."
        )
    return name


def auth_guard(expected_token: str):
    async def guard(
        authorization: str | None = Header(default=None),
        x_ge360_token: str | None = Header(default=None),
    ) -> None:
        if not expected_token:
            return
        candidate = x_ge360_token or ""
        if authorization and authorization.lower().startswith("bearer "):
            candidate = authorization[7:].strip()
        if not candidate or not hmac.compare_digest(candidate, expected_token):
            raise HTTPException(status_code=401, detail="Token GE360 non valido")

    return guard
