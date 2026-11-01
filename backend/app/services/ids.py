"""Deterministic, immutable, zero-padded IDs backed by a counter table."""
from __future__ import annotations
from sqlalchemy.orm import Session

from app.core.rules_config import ID_YEAR
from app.models import IdCounter


def next_seq(session: Session, key: str) -> int:
    row = session.get(IdCounter, key)
    if row is None:
        row = IdCounter(key=key, value=0)
        session.add(row)
    row.value += 1
    session.flush()
    return row.value


def yearly(session: Session, prefix: str) -> str:
    return f"{prefix}-{ID_YEAR}-{next_seq(session, prefix):06d}"


def applicant_id(s): return yearly(s, "APP")
def asset_id(s): return yearly(s, "AST")
def quote_id(s): return yearly(s, "QTE")
def policy_id(s): return yearly(s, "POL")
def decision_id(s): return yearly(s, "UWD")
def assessment_id(s): return yearly(s, "RAS")
def acceptance_id(s): return yearly(s, "ACC")
def payment_id(s): return yearly(s, "PAY")
def audit_id(s): return yearly(s, "AUD")


def gt_id(s): return f"GT-{next_seq(s, 'GT'):06d}"


def endorsement_id(s, policy_id_: str) -> str:
    return f"END-{policy_id_}-{next_seq(s, 'END:' + policy_id_):03d}"


def renewal_id(policy_id_: str, year: int) -> str:
    return f"REN-{policy_id_}-{year}"
