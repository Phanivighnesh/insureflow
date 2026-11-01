"""Policy lifecycle rules: transitions, issuance prerequisites, overlaps, renewals, endorsements."""
from __future__ import annotations
from datetime import date, timedelta
from decimal import Decimal

from app.core import rules_config as R

TRANSITIONS = {
    "DRAFT": {"PENDING_ACCEPTANCE", "CANCELLED"},
    "PENDING_ACCEPTANCE": {"PENDING_PAYMENT", "CANCELLED"},
    "PENDING_PAYMENT": {"ACTIVE", "CANCELLED"},
    "ACTIVE": {"CANCELLED", "EXPIRED", "RENEWED"},
    "EXPIRED": {"RENEWED"},
    "CANCELLED": set(),
    "RENEWED": set(),
}


def can_transition(frm: str | None, to: str) -> bool:
    if frm is None:
        return to in ("ACTIVE", "DRAFT")
    return to in TRANSITIONS.get(frm, set())


def compute_expiry(start: date) -> date:
    try:
        nxt = start.replace(year=start.year + 1)
    except ValueError:                      # 29 Feb
        nxt = start.replace(year=start.year + 1, day=28)
    return nxt - timedelta(days=1)


def check_issuance_prerequisites(*, quote_status, eligibility_status, decision_outcome,
                                 acceptance_recorded, payment_status, payment_amount,
                                 premium, blocking_exceptions=()) -> list[str]:
    """Return list of failed prerequisites (empty list => may issue)."""
    f = []
    if eligibility_status != "ELIGIBLE":
        f.append("Quote is not eligible")
    if decision_outcome != "APPROVED":
        f.append("Underwriting approval does not exist")
    if not acceptance_recorded or quote_status not in ("ACCEPTED",):
        f.append("Customer acceptance not recorded")
    if payment_status != "SUCCESS":
        f.append("Required payment condition not satisfied")
    elif premium is None or Decimal(str(payment_amount)) != Decimal(str(premium)):
        f.append("Payment amount does not match premium")
    for b in blocking_exceptions:
        f.append(f"Blocking exception: {b}")
    return f


def periods_overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start <= b_end and b_start <= a_end


def _effective_end(p: dict):
    return p["cancelled_on"] if p.get("status") == "CANCELLED" and p.get("cancelled_on") else p["expiry_date"]


def find_unauthorized_overlaps(policies: list[dict]) -> list[tuple[str, str]]:
    """policies: dicts with policy_id, asset_id, product_id, start_date, expiry_date, status,
    cancelled_on, overlap_reason, renewal_of_policy_id. A pair overlapping on the same
    asset+product is UNAUTHORIZED unless a permitted justification exists."""
    out = []
    ps = sorted(policies, key=lambda p: p["policy_id"])
    for i, a in enumerate(ps):
        for b in ps[i + 1:]:
            if a["asset_id"] != b["asset_id"] or a["product_id"] != b["product_id"]:
                continue
            if not periods_overlap(a["start_date"], _effective_end(a), b["start_date"], _effective_end(b)):
                continue
            if a.get("overlap_reason") or b.get("overlap_reason"):
                continue
            if a.get("renewal_of_policy_id") == b["policy_id"] or b.get("renewal_of_policy_id") == a["policy_id"]:
                continue
            out.append((a["policy_id"], b["policy_id"]))
    return out


def check_renewal_eligibility(*, policy_status, expiry_date, today, has_cancellation,
                              pending_payments, existing_open_renewal) -> tuple[list[str], list[str]]:
    """Returns (blocking, structural reasons -> no renewal record at all)."""
    blocking = []
    if policy_status == "CANCELLED" or has_cancellation:
        blocking.append("RENEWAL_FOR_CANCELLED_POLICY: cancelled policies cannot be renewed")
    elif policy_status != "ACTIVE":
        blocking.append(f"Policy status {policy_status} is not renewable")
    if not blocking:
        start_window = expiry_date - timedelta(days=R.RENEWAL_WINDOW_DAYS)
        if not (start_window <= today <= expiry_date):
            blocking.append(f"Outside renewal window ({start_window} to {expiry_date})")
    if existing_open_renewal:
        blocking.append("A renewal for this term already exists")
    return blocking, []


def check_endorsement_limits(product_key: str, coverage_code: str, new_coverage: float,
                             new_declared_value: float) -> list[str]:
    cfg, cov = R.PRODUCTS[product_key], R.COVERAGE_BY_CODE[coverage_code]
    v = []
    if new_coverage > cov["max_limit"] or new_coverage < cov["min_limit"]:
        v.append(f"ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT: coverage {new_coverage:,.0f} outside "
                 f"{cov['min_limit']:,}-{cov['max_limit']:,} for {coverage_code}")
    lo, hi = cfg["insured_value"]
    if not (lo <= new_declared_value <= hi):
        v.append(f"ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT: declared value {new_declared_value:,.0f} outside {lo:,}-{hi:,}")
    if new_coverage > new_declared_value * R.MAX_COVERAGE_TO_VALUE_RATIO + 1e-9:
        v.append("Coverage exceeds declared value")
    return v
