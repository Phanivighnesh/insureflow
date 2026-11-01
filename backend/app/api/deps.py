"""Demo-session authentication (HMAC-signed bearer tokens) and role-based dependencies.

DEMO ENVIRONMENT ONLY: customers self-issue an isolated session; staff roles require the configured
STAFF_ACCESS_CODE. This is not production authentication (no passwords, MFA, revocation)."""
from __future__ import annotations
import base64, hashlib, hmac, json, time
from typing import Iterator

from fastapi import Header, Request
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import STAFF_ROLES, Actor

STAFF = tuple(sorted(STAFF_ROLES))


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_token(settings, user_id: str, role: str, customer_key: str | None, now: float | None = None) -> str:
    body = _b64(json.dumps({"uid": user_id, "role": role, "ck": customer_key,
                            "exp": int((now or time.time()) + settings.session_ttl_hours * 3600)},
                           sort_keys=True).encode())
    sig = hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def verify_token(settings, token: str, now: float | None = None) -> Actor:
    try:
        body, sig = token.split(".", 1)
        good = hmac.new(settings.session_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good):
            raise ValueError("bad signature")
        data = json.loads(_unb64(body))
        if data["exp"] < (now or time.time()):
            raise UnauthorizedError("Session expired")
        return Actor(data["uid"], data["role"], data.get("ck"))
    except UnauthorizedError:
        raise
    except Exception:
        raise UnauthorizedError("Invalid or missing session token")


def get_db(request: Request) -> Iterator:
    """Request-scoped session. COMMIT happens in TransactionalRoute *before* the response is sent
    (dependency exit code runs after the response in current FastAPI, which allowed read-after-write races)."""
    session = request.app.state.session_factory()
    request.state.db = session
    try:
        yield session
    finally:
        session.close()                      # uncommitted work (errors / early exits) is discarded


class TransactionalRoute(APIRoute):
    """Commits (2xx/3xx) or rolls back (errors) the request session before the response is returned to the client."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                response = await original(request)
            except Exception:
                db = getattr(request.state, "db", None)
                if db is not None:
                    await run_in_threadpool(db.rollback)
                raise
            db = getattr(request.state, "db", None)
            if db is not None:
                await run_in_threadpool(db.commit if response.status_code < 400 else db.rollback)
            return response
        return handler


def current_actor(request: Request, authorization: str | None = Header(default=None)) -> Actor:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Authentication required: send 'Authorization: Bearer <token>'")
    return verify_token(request.app.state.settings, authorization[7:].strip())


def require_roles(*roles: str):
    def dep(request: Request, authorization: str | None = Header(default=None)) -> Actor:
        actor = current_actor(request, authorization)
        if actor.role not in roles:
            raise ForbiddenError(f"Role {actor.role} is not permitted; requires one of {', '.join(roles)}")
        return actor
    dep.allowed_roles = roles           # introspected by scripts/generate_api_contract.py
    return dep


customer_only = require_roles("CUSTOMER")
staff_only = require_roles(*STAFF)
reviewer_or_admin = require_roles("RISK_REVIEWER", "ADMINISTRATOR")
admin_only = require_roles("ADMINISTRATOR")
