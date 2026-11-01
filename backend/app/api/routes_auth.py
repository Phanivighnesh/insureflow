import secrets
from fastapi import APIRouter, Depends, Request

from app.api.deps import TransactionalRoute, create_token, current_actor
from app.core.errors import ForbiddenError
from app.core.security import STAFF_ROLES, Actor
from app.schemas.requests import SessionRequest

router = APIRouter(prefix="/api", tags=["auth"], route_class=TransactionalRoute)


@router.post("/auth/demo-session")
def demo_session(body: SessionRequest, request: Request):
    """DEMO ONLY. Customers receive an isolated session; staff roles need the staff access code."""
    s = request.app.state.settings
    if body.role in STAFF_ROLES:
        if not body.access_code or not secrets.compare_digest(body.access_code, s.staff_access_code):
            raise ForbiddenError("Invalid staff access code")
        customer_key, uid = None, f"{body.role.lower()}:{(body.display_name or 'staff').strip()[:30]}"
    else:
        customer_key = "ck_" + secrets.token_hex(10)
        uid = f"customer:{customer_key[3:11]}"
    token = create_token(s, uid, body.role, customer_key)
    return {"token": token, "role": body.role, "user_id": uid, "customer_key": customer_key,
            "display_name": body.display_name, "expires_in_hours": s.session_ttl_hours,
            "notice": "DEMO ENVIRONMENT - not production authentication"}


@router.get("/auth/me")
def me(actor: Actor = Depends(current_actor)):
    return {"user_id": actor.user_id, "role": actor.role, "customer_key": actor.customer_key}
