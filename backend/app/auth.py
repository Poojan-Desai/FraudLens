"""Small local-demo identity provider; credentials never enter the browser build."""
from dataclasses import dataclass
import hmac
import json
import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    actor: str
    role: str


def authenticate(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    try:
        configured = json.loads(os.environ.get("FRAUDLENS_CASE_TOKENS", "{}"))
        if not isinstance(configured, dict) or not configured:
            raise ValueError()
        for token, identity in configured.items():
            if len(token) < 32 or not isinstance(identity, dict) or set(identity) != {"actor", "role"}:
                raise ValueError()
            if not isinstance(identity["actor"], str) or not 1 <= len(identity["actor"]) <= 80 or identity["role"] not in {"viewer", "analyst", "admin"}:
                raise ValueError()
    except (ValueError, TypeError, KeyError):
        raise HTTPException(503, "Case access is unavailable; configure valid local credentials") from None
    if credentials:
        for token, identity in configured.items():
            if hmac.compare_digest(credentials.credentials.encode(), token.encode()):
                return Principal(**identity)
    raise HTTPException(401, "Valid bearer credentials required", headers={"WWW-Authenticate": "Bearer"})


def require_writer(principal: Principal = Depends(authenticate)) -> Principal:
    if principal.role not in {"analyst", "admin"}:
        raise HTTPException(403, "Analyst access required")
    return principal


def require_admin(principal: Principal = Depends(authenticate)) -> Principal:
    if principal.role != "admin":
        raise HTTPException(403, "Administrator access required")
    return principal
