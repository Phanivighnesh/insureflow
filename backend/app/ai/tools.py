"""Read-only retrieval tools for the AI Copilot.

Each tool accepts a SQLAlchemy *read-only* session and structured parameters,
and returns a GroundedContext with facts, record_refs, rules and limitations.

IMPORTANT: These functions MUST NOT:
- import or query GroundTruth
- call any workflow mutating function
- call session.add / session.delete / session.commit / session.flush
- import anything from app.services.workflow (except read helpers)
- import anything from app.services.evaluation
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.schemas import GroundedContext, RecordRef, SupportingRule
from app.core import rules_config as R
from app.models import (
    Applicant, AuditEvent, DetectedException, Endorsement,
    InsuredAsset, Payment, Policy, PolicyStatusHistory,
    Quote, QuoteAcceptance, RiskAssessment, Renewal, UnderwritingDecision,
    ValidationRun,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(x) -> float | None:
    return None if x is None else float(x)


def _route(kind: str, record_id: str) -> str:
    routes = {
        "quote": f"/ops/quotes/{record_id}",
        "policy": f"/ops/policies/{record_id}",
        "applicant": f"/ops/applicants/{record_id}",
        "exception": "/ops/exceptions",
        "endorsement": f"/ops/policies",
        "renewal": f"/ops/policies",
    }
    return routes.get(kind, "")


def _quote_ref(q: Quote) -> RecordRef:
    return RecordRef(type="quote", id=q.quote_id,
                     label=f"Quote {q.quote_id} ({q.status})",
                     ui_route=f"/ops/quotes/{q.quote_id}")


def _policy_ref(p: Policy) -> RecordRef:
    return RecordRef(type="policy", id=p.policy_id,
                     label=f"Policy {p.policy_id} ({p.status})",
                     ui_route=f"/ops/policies/{p.policy_id}")


def _applicant_ref(a: Applicant) -> RecordRef:
    return RecordRef(type="applicant", id=a.applicant_id,
                     label=f"Applicant {a.applicant_id}",
                     ui_route=f"/ops/applicants/{a.applicant_id}")


def _exception_ref(e: DetectedException) -> RecordRef:
    return RecordRef(type="exception", id=e.exception_id,
                     label=f"Exception {e.exception_id} ({e.issue_type})",
                     ui_route="/ops/exceptions")


def _rules_for_ids(rule_ids: list[str]) -> list[SupportingRule]:
    """Map stored rule IDs to human-readable text (built from known rules)."""
    results = []
    for rid in (rule_ids or []):
        text = _get_rule_text(rid)
        results.append(SupportingRule(rule_id=rid, text=text))
    return results


def _decisions_for(session: Session, quote_id: str) -> list[UnderwritingDecision]:
    return list(session.scalars(
        select(UnderwritingDecision)
        .where(UnderwritingDecision.quote_id == quote_id)
        .order_by(UnderwritingDecision.sequence)
    ).all())


# ---------------------------------------------------------------------------
# Tool: explain_decision
# ---------------------------------------------------------------------------

def tool_explain_decision(session: Session, quote_id: str) -> GroundedContext:
    q = session.get(Quote, quote_id)
    if q is None:
        return GroundedContext(intent="explain_decision", not_found=True,
                               limitations=[f"Quote {quote_id} was not found in the database."])

    decisions = _decisions_for(session, quote_id)
    cur = decisions[-1] if decisions else None
    ras = session.scalars(
        select(RiskAssessment).where(RiskAssessment.quote_id == quote_id)
        .order_by(RiskAssessment.assessment_id.desc())
    ).first()

    applicant = session.get(Applicant, q.applicant_id)
    product_key = R.PRODUCT_BY_ID.get(q.product_id, "UNKNOWN")

    facts: dict[str, Any] = {
        "quote_id": q.quote_id,
        "status": q.status,
        "product": product_key,
        "risk_score": q.risk_score,
        "risk_category": q.risk_category,
        "premium": _f(q.premium),
        "eligibility_status": q.eligibility_status,
        "rules_version": q.rules_version,
        "valid_until": str(q.valid_until) if q.valid_until else None,
    }

    if ras:
        facts["risk_factors"] = [
            {"code": rf.get("code"), "label": rf.get("label"),
             "sub_score": rf.get("sub_score"), "contribution": rf.get("contribution"),
             "penalised_missing": rf.get("penalised_missing")}
            for rf in (ras.factors or [])
        ][:10]
        facts["missing_info"] = ras.missing_info[:5] if ras.missing_info else []

    if cur:
        facts["current_decision"] = {
            "outcome": cur.outcome,
            "decision_type": cur.decision_type,
            "approval_authority": cur.approval_authority,
            "reasons": cur.reasons,
            "rule_ids": cur.rule_ids,
            "decided_at": str(cur.decided_at),
            "decided_role": cur.decided_role,
        }
        # Withold premium for declined quotes (labelled as indicative for staff)
        if q.status == "DECLINED":
            facts["premium_note"] = "indicative, not offered"
    else:
        facts["current_decision"] = None

    # Decision history summary
    facts["decision_history"] = [
        {"sequence": d.sequence, "outcome": d.outcome, "decided_at": str(d.decided_at)}
        for d in decisions
    ]

    refs = [_quote_ref(q)]
    if applicant:
        refs.append(_applicant_ref(applicant))

    rules = []
    if cur:
        rules = _rules_for_ids(cur.rule_ids)

    limitations = []
    if q.status == "DECLINED" and q.premium:
        limitations.append("Premium shown is indicative only — this quote was declined and is not offered.")

    confidence = "high" if cur and ras else "medium" if cur else "low"

    return GroundedContext(intent="explain_decision", facts=facts, record_refs=refs,
                           rules=rules, limitations=limitations, confidence=confidence)


# ---------------------------------------------------------------------------
# Tool: applicant_risk_profile
# ---------------------------------------------------------------------------

def tool_applicant_risk_profile(session: Session, applicant_id: str) -> GroundedContext:
    applicant = session.get(Applicant, applicant_id)
    if applicant is None:
        return GroundedContext(intent="applicant_risk_profile", not_found=True,
                               limitations=[f"Applicant {applicant_id} was not found."])

    assets = list(session.scalars(
        select(InsuredAsset).where(InsuredAsset.applicant_id == applicant_id)
    ).all())

    quotes = list(session.scalars(
        select(Quote).where(Quote.applicant_id == applicant_id)
        .order_by(Quote.created_at.desc())
    ).all())[:10]

    policies = list(session.scalars(
        select(Policy).where(Policy.applicant_id == applicant_id)
        .order_by(Policy.issued_at.desc())
    ).all())[:5]

    facts: dict[str, Any] = {
        "applicant_id": applicant.applicant_id,
        "applicant_type": applicant.applicant_type,
        "age": applicant.age,
        "location": applicant.location,
        "status": applicant.status,
        "asset_count": len(assets),
        "quote_count": len(quotes),
        "policy_count": len(policies),
        "assets": [
            {"asset_id": a.asset_id, "asset_type": a.asset_type,
             "declared_value": _f(a.declared_value), "location": a.location,
             "status": a.status}
            for a in assets[:5]
        ],
        "recent_quotes": [
            {"quote_id": q.quote_id, "status": q.status, "product": R.PRODUCT_BY_ID.get(q.product_id),
             "risk_score": q.risk_score, "risk_category": q.risk_category}
            for q in quotes[:5]
        ],
        "policies": [
            {"policy_id": p.policy_id, "status": p.status, "product": R.PRODUCT_BY_ID.get(p.product_id),
             "premium": _f(p.premium)}
            for p in policies
        ],
    }

    # Latest risk assessment across all quotes
    risk_scores = [q.risk_score for q in quotes if q.risk_score is not None]
    if risk_scores:
        facts["max_risk_score"] = max(risk_scores)
        facts["avg_risk_score"] = round(sum(risk_scores) / len(risk_scores), 2)

    refs = [_applicant_ref(applicant)]
    refs += [_quote_ref(q) for q in quotes[:3]]
    refs += [_policy_ref(p) for p in policies[:3]]

    confidence = "high" if quotes else "medium"
    return GroundedContext(intent="applicant_risk_profile", facts=facts, record_refs=refs,
                           confidence=confidence)


# ---------------------------------------------------------------------------
# Tool: premium_explanation
# ---------------------------------------------------------------------------

def tool_premium_explanation(session: Session, quote_id: str) -> GroundedContext:
    q = session.get(Quote, quote_id)
    if q is None:
        return GroundedContext(intent="premium_explanation", not_found=True,
                               limitations=[f"Quote {quote_id} was not found."])

    facts: dict[str, Any] = {
        "quote_id": q.quote_id,
        "status": q.status,
        "product": R.PRODUCT_BY_ID.get(q.product_id, "UNKNOWN"),
        "coverage_code": q.coverage_code,
        "premium": _f(q.premium),
        "premium_breakdown": q.premium_breakdown,
        "rules_version": q.rules_version,
        "risk_score": q.risk_score,
        "risk_category": q.risk_category,
    }

    limitations = []
    if q.status == "DECLINED":
        limitations.append("This quote was declined. The premium shown is indicative only and was not offered.")
    if q.premium is None:
        limitations.append("No premium has been calculated for this quote yet.")

    refs = [_quote_ref(q)]
    confidence = "high" if q.premium_breakdown else "medium" if q.premium else "low"
    return GroundedContext(intent="premium_explanation", facts=facts, record_refs=refs,
                           limitations=limitations, confidence=confidence)


# ---------------------------------------------------------------------------
# Tool: anomaly_explanation
# ---------------------------------------------------------------------------

def tool_anomaly_explanation(session: Session, exception_id: str) -> GroundedContext:
    exc = session.get(DetectedException, exception_id)
    if exc is None:
        return GroundedContext(intent="anomaly_explanation", not_found=True,
                               limitations=[f"Exception {exception_id} was not found."])

    facts: dict[str, Any] = {
        "exception_id": exc.exception_id,
        "issue_type": exc.issue_type,
        "affected_entity": exc.affected_entity,
        "affected_record_id": exc.affected_record_id,
        "severity": exc.severity,
        "expected_outcome": exc.expected_outcome,
        "actual_outcome": exc.actual_outcome,
        "resolution_status": exc.resolution_status,
        "detected_at": str(exc.detected_at),
        "record_date": str(exc.record_date) if exc.record_date else None,
        "details": exc.details,
    }

    refs = [_exception_ref(exc)]
    # Link to the affected record
    entity = exc.affected_entity
    rid = exc.affected_record_id
    if entity == "Quote":
        refs.append(RecordRef(type="quote", id=rid, label=f"Affected quote {rid}",
                               ui_route=f"/ops/quotes/{rid}"))
    elif entity == "Policy":
        refs.append(RecordRef(type="policy", id=rid, label=f"Affected policy {rid}",
                               ui_route=f"/ops/policies/{rid}"))
    elif entity == "Applicant":
        refs.append(RecordRef(type="applicant", id=rid, label=f"Affected applicant {rid}",
                               ui_route=f"/ops/applicants/{rid}"))

    return GroundedContext(intent="anomaly_explanation", facts=facts, record_refs=refs,
                           confidence="high")


# ---------------------------------------------------------------------------
# Tool: anomaly_summary
# ---------------------------------------------------------------------------

def tool_anomaly_summary(session: Session) -> GroundedContext:
    # Latest validation run
    latest_run = session.scalars(
        select(ValidationRun).order_by(ValidationRun.started_at.desc())
    ).first()

    if latest_run is None:
        return GroundedContext(intent="anomaly_summary", not_found=True,
                               limitations=["No validation runs found. Run a validation first."])

    # Count by issue_type
    by_type = dict(session.execute(
        select(DetectedException.issue_type, func.count().label("cnt"))
        .where(DetectedException.run_id == latest_run.run_id)
        .group_by(DetectedException.issue_type)
    ).all())

    # Count by severity
    by_severity = dict(session.execute(
        select(DetectedException.severity, func.count().label("cnt"))
        .where(DetectedException.run_id == latest_run.run_id)
        .group_by(DetectedException.severity)
    ).all())

    # Count by resolution
    by_resolution = dict(session.execute(
        select(DetectedException.resolution_status, func.count().label("cnt"))
        .where(DetectedException.run_id == latest_run.run_id)
        .group_by(DetectedException.resolution_status)
    ).all())

    # Sample a few
    samples = list(session.scalars(
        select(DetectedException)
        .where(DetectedException.run_id == latest_run.run_id)
        .order_by(DetectedException.severity, DetectedException.exception_id)
    ).all())[:10]

    facts: dict[str, Any] = {
        "run_id": latest_run.run_id,
        "validated_at": str(latest_run.finished_at),
        "total_findings": latest_run.finding_count,
        "by_issue_type": by_type,
        "by_severity": by_severity,
        "by_resolution": by_resolution,
        "sample_exceptions": [
            {"exception_id": e.exception_id, "issue_type": e.issue_type,
             "severity": e.severity, "affected_entity": e.affected_entity,
             "resolution_status": e.resolution_status}
            for e in samples
        ],
    }

    # Include evaluation metrics if stored (these are already-computed, not ground truth)
    if latest_run.evaluation:
        facts["evaluation_report"] = {
            k: v for k, v in latest_run.evaluation.items()
            if k not in ("per_issue_type",)  # keep top-level numbers only
        }
        facts["evaluation_note"] = (
            "These metrics compare the detector's findings to the stored evaluation labels. "
            "They are NOT used by the detector — they measure its accuracy retrospectively."
        )

    refs = [_exception_ref(e) for e in samples[:5]]
    confidence = "high"
    return GroundedContext(intent="anomaly_summary", facts=facts, record_refs=refs,
                           confidence=confidence)


# ---------------------------------------------------------------------------
# Tool: policy_history
# ---------------------------------------------------------------------------

def tool_policy_history(session: Session, policy_id: str) -> GroundedContext:
    p = session.get(Policy, policy_id)
    if p is None:
        return GroundedContext(intent="policy_history", not_found=True,
                               limitations=[f"Policy {policy_id} was not found."])

    history = list(session.scalars(
        select(PolicyStatusHistory).where(PolicyStatusHistory.policy_id == policy_id)
        .order_by(PolicyStatusHistory.history_id)
    ).all())

    endorsements = list(session.scalars(
        select(Endorsement).where(Endorsement.policy_id == policy_id)
        .order_by(Endorsement.endorsement_id)
    ).all())[:10]

    renewals = list(session.scalars(
        select(Renewal).where(Renewal.policy_id == policy_id)
        .order_by(Renewal.renewal_id)
    ).all())[:5]

    payments = list(session.scalars(
        select(Payment).where(Payment.policy_id == policy_id)
        .order_by(Payment.payment_id)
    ).all())[:10]

    facts: dict[str, Any] = {
        "policy_id": p.policy_id,
        "status": p.status,
        "product": R.PRODUCT_BY_ID.get(p.product_id, "UNKNOWN"),
        "coverage_amount": _f(p.coverage_amount),
        "premium": _f(p.premium),
        "start_date": str(p.start_date),
        "expiry_date": str(p.expiry_date),
        "cancelled_at": str(p.cancelled_at) if p.cancelled_at else None,
        "cancellation_reason": p.cancellation_reason,
        "renewal_of_policy_id": p.renewal_of_policy_id,
        "status_history": [
            {"from": h.from_status, "to": h.to_status, "at": str(h.changed_at),
             "by": h.changed_by}
            for h in history
        ],
        "endorsement_count": len(endorsements),
        "endorsements": [
            {"endorsement_id": e.endorsement_id, "type": e.endorsement_type,
             "status": e.status, "effective_date": str(e.effective_date),
             "coverage_after": _f(e.coverage_after)}
            for e in endorsements
        ],
        "renewal_count": len(renewals),
        "renewals": [
            {"renewal_id": r.renewal_id, "status": r.status,
             "new_start_date": str(r.new_start_date),
             "offered_premium": _f(r.offered_premium)}
            for r in renewals
        ],
        "payment_count": len(payments),
        "payments": [
            {"payment_id": pay.payment_id, "amount": _f(pay.amount),
             "status": pay.status, "created_at": str(pay.created_at)}
            for pay in payments
        ],
    }

    refs = [_policy_ref(p)]
    if p.quote_id:
        q = session.get(Quote, p.quote_id)
        if q:
            refs.append(_quote_ref(q))
    applicant = session.get(Applicant, p.applicant_id)
    if applicant:
        refs.append(_applicant_ref(applicant))

    return GroundedContext(intent="policy_history", facts=facts, record_refs=refs,
                           confidence="high")


# ---------------------------------------------------------------------------
# Tool: renewal_explanation
# ---------------------------------------------------------------------------

def tool_renewal_explanation(session: Session, renewal_id: str) -> GroundedContext:
    renewal = session.get(Renewal, renewal_id)
    if renewal is None:
        # Try to find renewal by policy_id
        return GroundedContext(intent="renewal_explanation", not_found=True,
                               limitations=[f"Renewal {renewal_id} was not found."])

    policy = session.get(Policy, renewal.policy_id)
    facts: dict[str, Any] = {
        "renewal_id": renewal.renewal_id,
        "policy_id": renewal.policy_id,
        "status": renewal.status,
        "eligibility_status": renewal.eligibility_status,
        "reasons": renewal.reasons,
        "offered_premium": _f(renewal.offered_premium),
        "risk_score": renewal.risk_score,
        "new_start_date": str(renewal.new_start_date),
        "new_expiry_date": str(renewal.new_expiry_date),
        "generated_at": str(renewal.generated_at),
        "responded_at": str(renewal.responded_at) if renewal.responded_at else None,
        "response_reason": renewal.response_reason,
        "new_policy_id": renewal.new_policy_id,
    }

    refs = [RecordRef(type="renewal", id=renewal.renewal_id,
                      label=f"Renewal {renewal.renewal_id} ({renewal.status})",
                      ui_route=f"/ops/policies/{renewal.policy_id}")]
    if policy:
        refs.append(_policy_ref(policy))

    confidence = "high" if renewal.reasons else "medium"
    return GroundedContext(intent="renewal_explanation", facts=facts, record_refs=refs,
                           confidence=confidence)


# ---------------------------------------------------------------------------
# Tool: audit_summary
# ---------------------------------------------------------------------------

def tool_audit_summary(session: Session, entity_type: str, entity_id: str) -> GroundedContext:
    events = list(session.scalars(
        select(AuditEvent)
        .where(AuditEvent.entity_id == entity_id)
        .order_by(AuditEvent.occurred_at)
    ).all())[:25]

    if not events:
        # Broaden search: find events that mention this entity
        events = list(session.scalars(
            select(AuditEvent)
            .where(AuditEvent.entity_type == entity_type)
            .order_by(AuditEvent.occurred_at.desc())
        ).all())[:10]

    facts: dict[str, Any] = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "event_count": len(events),
        "events": [
            {"audit_id": e.audit_id, "event_type": e.event_type,
             "actor": e.actor, "actor_role": e.actor_role,
             "occurred_at": str(e.occurred_at)}
            for e in events
        ],
    }

    refs: list[RecordRef] = []
    if entity_type.lower() == "quote":
        refs.append(RecordRef(type="quote", id=entity_id,
                               label=f"Quote {entity_id}",
                               ui_route=f"/ops/quotes/{entity_id}"))
    elif entity_type.lower() == "policy":
        refs.append(RecordRef(type="policy", id=entity_id,
                               label=f"Policy {entity_id}",
                               ui_route=f"/ops/policies/{entity_id}"))

    limitations = []
    if len(events) == 25:
        limitations.append("Audit trail capped at 25 most recent events.")

    confidence = "high" if events else "low"
    return GroundedContext(intent="audit_summary", facts=facts, record_refs=refs,
                           limitations=limitations, confidence=confidence)


# ---------------------------------------------------------------------------
# Tool: senior_review_queue
# ---------------------------------------------------------------------------

def tool_senior_review_queue(session: Session) -> GroundedContext:
    pending = list(session.scalars(
        select(Quote)
        .where(Quote.status == "REFERRED")
        .order_by(Quote.created_at)
    ).all())

    senior_pending = []
    for q in pending:
        decisions = _decisions_for(session, q.quote_id)
        cur = decisions[-1] if decisions else None
        if cur and cur.approval_authority == "SENIOR_UNDERWRITER":
            senior_pending.append((q, cur))

    facts: dict[str, Any] = {
        "total_referred": len(pending),
        "senior_review_required": len(senior_pending),
        "items": [
            {
                "quote_id": q.quote_id,
                "product": R.PRODUCT_BY_ID.get(q.product_id, "UNKNOWN"),
                "risk_score": q.risk_score,
                "risk_category": q.risk_category,
                "premium": _f(q.premium),
                "created_at": str(q.created_at),
                "reasons": d.reasons[:3] if d.reasons else [],
                "rule_ids": d.rule_ids[:3] if d.rule_ids else [],
            }
            for q, d in senior_pending[:20]
        ],
    }

    refs = [_quote_ref(q) for q, _ in senior_pending[:10]]
    confidence = "high"
    return GroundedContext(intent="senior_review_queue", facts=facts, record_refs=refs,
                           confidence=confidence)


# ---------------------------------------------------------------------------
# Tool: aggregate_insight
# ---------------------------------------------------------------------------

def tool_aggregate_insight(session: Session, product_key: str | None = None,
                            risk_category: str | None = None) -> GroundedContext:
    """Compute backend aggregates: top rule IDs and risk factors among filtered quotes."""
    stmt = select(Quote)
    if product_key and product_key.upper() in R.PRODUCTS:
        prod_id = R.PRODUCTS[product_key.upper()]["product_id"]
        stmt = stmt.where(Quote.product_id == prod_id)
    if risk_category and risk_category.upper() in ("LOW", "MEDIUM", "HIGH"):
        stmt = stmt.where(Quote.risk_category == risk_category.upper())

    quotes = list(session.scalars(stmt).all())

    # Aggregate rule IDs from decisions
    from collections import Counter
    rule_counter: Counter = Counter()
    outcome_counter: Counter = Counter()

    for q in quotes[:500]:  # cap for performance
        outcome_counter[q.status] += 1
        decisions = _decisions_for(session, q.quote_id)
        if decisions:
            cur = decisions[-1]
            for rid in (cur.rule_ids or []):
                rule_counter[rid] += 1

    top_rules = rule_counter.most_common(10)

    facts: dict[str, Any] = {
        "filter_product": product_key,
        "filter_risk_category": risk_category,
        "total_quotes_analyzed": len(quotes),
        "outcome_distribution": dict(outcome_counter),
        "top_rule_ids": [{"rule_id": rid, "count": cnt} for rid, cnt in top_rules],
        "avg_risk_score": (
            round(sum(q.risk_score for q in quotes if q.risk_score) /
                  max(1, sum(1 for q in quotes if q.risk_score)), 2)
            if any(q.risk_score for q in quotes) else None
        ),
    }

    rules = [
        SupportingRule(rule_id=rid, text=_get_rule_text(rid))
        for rid, _ in top_rules[:5]
    ]

    confidence = "high" if quotes else "low"
    limitations = ["Aggregate limited to up to 500 quotes for performance."] if len(quotes) > 499 else []

    return GroundedContext(intent="aggregate_insight", facts=facts, record_refs=[],
                           rules=rules, limitations=limitations, confidence=confidence)


# ---------------------------------------------------------------------------
# Tool: rules_help
# ---------------------------------------------------------------------------

def tool_rules_help(question: str) -> GroundedContext:
    """Return relevant rules from rules_config — never hard-code values here."""
    lo = question.lower()

    # Build a structured rules snapshot from rules_config
    rules_snapshot: dict[str, Any] = {
        "rules_version": R.RULES_VERSION,
        "risk_thresholds": R.RISK_THRESHOLDS,
        "decline_risk_score": R.DECLINE_RISK_SCORE,
        "missing_risk_penalty": R.MISSING_RISK_PENALTY,
        "approval_authority_levels": R.AUTHORITY_LEVELS,
        "role_authority": R.ROLE_AUTHORITY,
        "risk_category_authority": R.RISK_CATEGORY_AUTHORITY,
        "quote_validity_days": R.QUOTE_VALIDITY_DAYS,
        "renewal_window_days": R.RENEWAL_WINDOW_DAYS,
        "claims_factor_table": R.CLAIMS_FACTOR,
        "risk_category_factor": R.RISK_CATEGORY_FACTOR,
    }

    # Add product-specific limits if queried
    product_limits = {}
    for key, prod in R.PRODUCTS.items():
        product_limits[key] = {
            "auto_approval_limit": prod.get("auto_approval_limit"),
            "analyst_limit": prod.get("analyst_limit"),
            "reviewer_limit": prod.get("reviewer_limit"),
            "base_rate": prod.get("base_rate"),
            "fixed_charges": prod.get("fixed_charges"),
        }
    rules_snapshot["product_limits"] = product_limits

    # Exception rules
    rules_snapshot["exception_rules"] = {
        rid: {"message": rv["message"], "authority": rv["authority"]}
        for rid, rv in R.EXCEPTION_RULES.items()
    }

    supporting = [
        SupportingRule(rule_id="RULES_VERSION", text=f"Rules version: {R.RULES_VERSION}"),
        SupportingRule(rule_id="DECLINE_THRESHOLD",
                       text=f"Auto-decline threshold: risk score >= {R.DECLINE_RISK_SCORE}"),
        SupportingRule(rule_id="MISSING_RISK_PENALTY",
                       text=f"Missing information penalty: {R.MISSING_RISK_PENALTY}"),
    ]

    return GroundedContext(intent="rules_help", facts=rules_snapshot, record_refs=[],
                           rules=supporting, confidence="high")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_rule_text(rule_id: str) -> str:
    """Return human-readable text for a rule ID."""
    _KNOWN_RULES = {
        "UW-APR-001": "Low risk and coverage within auto-approval limit — approved automatically",
        "UW-DEC-001": "Application ineligible under product rules",
        "UW-DEC-002": f"Risk score >= decline threshold ({R.DECLINE_RISK_SCORE})",
        "UW-PEN-001": "Mandatory information missing — pending information",
        "UW-REF-RISK": "Risk category requires manual underwriting review",
        "UW-REF-COV": "Coverage amount exceeds auto-approval limit",
        "UW-REF-CLAIMS": R.EXCEPTION_RULES.get("UW-REF-CLAIMS", {}).get("message", "Claims history triggers review"),
    }
    return _KNOWN_RULES.get(rule_id, rule_id)


# ---------------------------------------------------------------------------
# Dispatcher: select and call the right tool(s)
# ---------------------------------------------------------------------------

def call_tools(session: Session, parsed) -> GroundedContext:
    """Dispatch to the appropriate read-only tool based on parsed intent."""
    intent = parsed.intent

    if intent == "explain_decision":
        qid = parsed.quote_ids[0] if parsed.quote_ids else None
        if qid:
            return tool_explain_decision(session, qid)
        return GroundedContext(intent=intent, not_found=True,
                               limitations=["No quote ID found in the question."])

    elif intent == "applicant_risk_profile":
        aid = parsed.applicant_ids[0] if parsed.applicant_ids else None
        if aid:
            return tool_applicant_risk_profile(session, aid)
        # If context is a quote, try to get applicant from there
        if parsed.quote_ids:
            q = session.get(Quote, parsed.quote_ids[0])
            if q:
                return tool_applicant_risk_profile(session, q.applicant_id)
        return GroundedContext(intent=intent, not_found=True,
                               limitations=["No applicant ID found in the question."])

    elif intent == "premium_explanation":
        qid = parsed.quote_ids[0] if parsed.quote_ids else None
        if qid:
            return tool_premium_explanation(session, qid)
        return GroundedContext(intent=intent, not_found=True,
                               limitations=["No quote ID found in the question."])

    elif intent == "anomaly_explanation":
        eid = parsed.exception_ids[0] if parsed.exception_ids else None
        if eid:
            return tool_anomaly_explanation(session, eid)
        return GroundedContext(intent=intent, not_found=True,
                               limitations=["No exception ID found in the question."])

    elif intent == "anomaly_summary":
        return tool_anomaly_summary(session)

    elif intent == "policy_history":
        pid = parsed.policy_ids[0] if parsed.policy_ids else None
        if pid:
            return tool_policy_history(session, pid)
        return GroundedContext(intent=intent, not_found=True,
                               limitations=["No policy ID found in the question."])

    elif intent == "renewal_explanation":
        rid = parsed.renewal_ids[0] if parsed.renewal_ids else None
        if rid:
            return tool_renewal_explanation(session, rid)
        # Try to find via policy
        if parsed.policy_ids:
            pol = parsed.policy_ids[0]
            renewal = session.scalars(
                select(Renewal).where(Renewal.policy_id == pol)
                .order_by(Renewal.renewal_id.desc())
            ).first()
            if renewal:
                return tool_renewal_explanation(session, renewal.renewal_id)
        return GroundedContext(intent=intent, not_found=True,
                               limitations=["No renewal or policy ID found in the question."])

    elif intent == "audit_summary":
        if parsed.quote_ids:
            return tool_audit_summary(session, "Quote", parsed.quote_ids[0])
        if parsed.policy_ids:
            return tool_audit_summary(session, "Policy", parsed.policy_ids[0])
        return GroundedContext(intent=intent, not_found=True,
                               limitations=["No quote or policy ID found for audit trail."])

    elif intent == "senior_review_queue":
        return tool_senior_review_queue(session)

    elif intent == "aggregate_insight":
        # Try to detect product filter from question
        lo = parsed.context_type or ""
        q_text = ""  # We'll pass no question text here; filters come from context
        product_key = None
        risk_category = None
        return tool_aggregate_insight(session, product_key, risk_category)

    elif intent == "rules_help":
        # We need the original question for context — pass via context
        return tool_rules_help("")

    else:  # unsupported
        return GroundedContext(
            intent="unsupported",
            facts={},
            limitations=[
                "This question type is not supported. The copilot can answer: "
                "explain_decision, applicant_risk_profile, premium_explanation, "
                "anomaly_explanation, anomaly_summary, policy_history, "
                "renewal_explanation, audit_summary, senior_review_queue, "
                "aggregate_insight, rules_help."
            ],
            confidence="low",
        )
