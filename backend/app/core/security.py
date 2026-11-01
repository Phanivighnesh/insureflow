"""Demo-grade authorization primitives (NOT production authentication).

An Actor is resolved by the API layer from a demo session. Customers are isolated
by `customer_key` (an opaque per-session value stored on Applicant.owner_key).
"""
from __future__ import annotations
from dataclasses import dataclass

from app.core.errors import ForbiddenError

STAFF_ROLES = frozenset({"OPERATIONS_ANALYST", "RISK_REVIEWER", "ADMINISTRATOR"})


@dataclass(frozen=True)
class Actor:
    user_id: str
    role: str
    customer_key: str | None = None


SYSTEM = Actor("SYSTEM", "SYSTEM")


def is_staff(actor: Actor) -> bool:
    return actor.role in STAFF_ROLES


def require_staff(actor: Actor) -> None:
    if not is_staff(actor):
        raise ForbiddenError("This action requires an internal operations role")


def assert_can_access_applicant(actor: Actor, applicant) -> None:
    """Staff may see everything; customers only records they own (no ID-guessing)."""
    if actor.role == "SYSTEM" or is_staff(actor):
        return
    if actor.role == "CUSTOMER" and actor.customer_key and applicant.owner_key == actor.customer_key:
        return
    raise ForbiddenError("You do not have access to this record")
