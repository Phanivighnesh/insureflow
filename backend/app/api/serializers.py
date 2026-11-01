"""ORM -> JSON-able dicts. Presentation only; all decisions come from engines/workflow."""
from __future__ import annotations
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import rules_config as R
from app.models import (Applicant, AuditEvent, CoverageOption, Endorsement, InsuredAsset, Payment, Policy,
                        PolicyStatusHistory, Quote, QuoteAcceptance, Renewal, RiskAssessment, UnderwritingDecision)


def f(x):
    return None if x is None else float(x)


def paginate(session: Session, stmt, page: int, page_size: int, mapper):
    page, page_size = max(1, page), min(max(1, page_size), 200)
    total = session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = session.execute(stmt.limit(page_size).offset((page - 1) * page_size)).all()
    return {"items": [mapper(*r) if len(r) > 1 else mapper(r[0]) for r in rows],
            "total": total, "page": page, "page_size": page_size}


def decision_dict(d: UnderwritingDecision) -> dict:
    return {"decision_id": d.decision_id, "quote_id": d.quote_id, "sequence": d.sequence, "outcome": d.outcome,
            "decision_type": d.decision_type, "risk_score": d.risk_score, "reasons": d.reasons,
            "rule_ids": d.rule_ids, "approval_authority": d.approval_authority, "decided_by": d.decided_by,
            "decided_role": d.decided_role, "notes": d.notes, "decided_at": d.decided_at,
            "rule_engine_version": d.rule_engine_version}


def decisions_for(session, quote_id):
    return session.scalars(select(UnderwritingDecision).where(UnderwritingDecision.quote_id == quote_id)
                           .order_by(UnderwritingDecision.sequence)).all()


def next_steps(q: Quote, cur: UnderwritingDecision | None) -> list[str]:
    s = q.status
    if s == "APPROVED":
        return ["Review the premium and coverage, then accept the quote.", "After acceptance, complete the DEMO payment to issue your policy."]
    if s == "REFERRED":
        return [f"Your application is awaiting manual underwriting review ({cur.approval_authority.replace('_', ' ').title()} authority)."]
    if s == "DECLINED":
        return ["This application was declined under the product rules; see the reasons above."]
    if s == "PENDING_INFORMATION":
        missing = (q.eligibility_detail or {}).get("missing_fields", [])
        return ["Provide the missing information to continue: " + (", ".join(missing) or "see eligibility checks")]
    if s == "ACCEPTED":
        return ["Quote accepted. Complete the DEMO payment to issue the policy."]
    if s == "POLICY_ISSUED":
        return ["Policy issued. View it in your policy dashboard."]
    return []


def quote_summary(q: Quote, applicant: Applicant | None = None, cur: UnderwritingDecision | None = None,
                  for_customer=False) -> dict:
    hide = for_customer and q.status == "DECLINED"
    d = {"quote_id": q.quote_id, "applicant_id": q.applicant_id, "asset_id": q.asset_id,
         "product_key": R.PRODUCT_BY_ID.get(q.product_id), "product_id": q.product_id,
         "coverage_code": q.coverage_code, "requested_coverage": f(q.requested_coverage), "status": q.status,
         "eligibility_status": q.eligibility_status, "risk_score": q.risk_score, "risk_category": q.risk_category,
         "premium": None if hide else f(q.premium), "valid_until": q.valid_until, "created_at": q.created_at}
    if applicant is not None:
        d["applicant_name"] = applicant.full_name
    if cur is not None:
        d["decision_outcome"], d["required_authority"] = cur.outcome, cur.approval_authority
    return d


def quote_detail(session: Session, q: Quote, for_customer=False) -> dict:
    applicant = session.get(Applicant, q.applicant_id)
    asset = session.get(InsuredAsset, q.asset_id)
    decs = decisions_for(session, q.quote_id)
    cur = decs[-1] if decs else None
    ras = session.scalars(select(RiskAssessment).where(RiskAssessment.quote_id == q.quote_id)
                          .order_by(RiskAssessment.assessment_id.desc())).first()
    acc = session.scalars(select(QuoteAcceptance).where(QuoteAcceptance.quote_id == q.quote_id)).first()
    pol = session.scalars(select(Policy).where(Policy.quote_id == q.quote_id)).first()
    pays = session.scalars(select(Payment).where(Payment.quote_id == q.quote_id).order_by(Payment.payment_id)).all()
    out = quote_summary(q, applicant, cur, for_customer)
    out.update({
        "applicant": {"applicant_id": applicant.applicant_id, "full_name": applicant.full_name, "email": applicant.email,
                      "phone": applicant.phone, "age": applicant.age, "location": applicant.location},
        "asset": {"asset_id": asset.asset_id, "asset_type": asset.asset_type, "declared_value": f(asset.declared_value),
                  "location": asset.location, "attributes": asset.attributes},
        "eligibility": q.eligibility_detail,
        "risk": None if ras is None else {"score": ras.score, "category": ras.category, "factors": ras.factors,
                                          "missing_info": ras.missing_info, "explanation": ras.explanation,
                                          "assessed_at": ras.assessed_at},
        "premium_breakdown": None if (for_customer and q.status == "DECLINED") else q.premium_breakdown,
        "decision": decision_dict(cur) if cur else None,
        "decision_history": [decision_dict(d) for d in decs],
        "acceptance": None if not acc else {"acceptance_id": acc.acceptance_id, "accepted_at": acc.accepted_at,
                                            "accepted_by": acc.accepted_by, "terms_version": acc.terms_version},
        "payments": [payment_dict(p) for p in pays], "policy_id": pol.policy_id if pol else None,
        "next_steps": next_steps(q, cur), "rules_version": q.rules_version,
        "demo_notice": "DEMO ENVIRONMENT - synthetic rules, demo payments only",
    })
    return out


def payment_dict(p: Payment) -> dict:
    return {"payment_id": p.payment_id, "quote_id": p.quote_id, "policy_id": p.policy_id, "renewal_id": p.renewal_id,
            "amount": f(p.amount), "status": p.status, "method": p.method, "is_demo": p.is_demo,
            "created_at": p.created_at}


def policy_summary(p: Policy, applicant: Applicant | None = None) -> dict:
    d = {"policy_id": p.policy_id, "quote_id": p.quote_id, "applicant_id": p.applicant_id, "asset_id": p.asset_id,
         "product_key": R.PRODUCT_BY_ID.get(p.product_id), "coverage_id": p.coverage_id,
         "coverage_amount": f(p.coverage_amount), "premium": f(p.premium), "status": p.status,
         "start_date": p.start_date, "expiry_date": p.expiry_date, "cancelled_at": p.cancelled_at,
         "renewal_of_policy_id": p.renewal_of_policy_id}
    if applicant is not None:
        d["applicant_name"] = applicant.full_name
    return d


def endorsement_dict(e: Endorsement) -> dict:
    return {"endorsement_id": e.endorsement_id, "policy_id": e.policy_id, "endorsement_type": e.endorsement_type,
            "requested_changes": e.requested_changes, "coverage_before": f(e.coverage_before),
            "coverage_after": f(e.coverage_after), "declared_value_before": f(e.declared_value_before),
            "declared_value_after": f(e.declared_value_after), "premium_before": f(e.premium_before),
            "premium_after": f(e.premium_after), "status": e.status, "effective_date": e.effective_date,
            "requested_by": e.requested_by, "requested_at": e.requested_at, "decided_by": e.decided_by,
            "decided_at": e.decided_at, "decision_reason": e.decision_reason}


def renewal_dict(r: Renewal, policy: Policy | None = None) -> dict:
    d = {"renewal_id": r.renewal_id, "policy_id": r.policy_id, "renewal_year": r.renewal_year,
         "new_start_date": r.new_start_date, "new_expiry_date": r.new_expiry_date,
         "coverage_amount": f(r.coverage_amount), "offered_premium": f(r.offered_premium),
         "risk_score": r.risk_score, "eligibility_status": r.eligibility_status, "reasons": r.reasons,
         "status": r.status, "new_policy_id": r.new_policy_id, "generated_at": r.generated_at,
         "responded_at": r.responded_at, "response_reason": r.response_reason}
    if policy is not None:
        d["policy_expiry_date"] = policy.expiry_date
    return d


def audit_dict(a: AuditEvent) -> dict:
    return {"audit_id": a.audit_id, "entity_type": a.entity_type, "entity_id": a.entity_id,
            "event_type": a.event_type, "actor": a.actor, "actor_role": a.actor_role, "payload": a.payload,
            "occurred_at": a.occurred_at}


def history_dict(h: PolicyStatusHistory) -> dict:
    return {"from_status": h.from_status, "to_status": h.to_status, "changed_at": h.changed_at,
            "changed_by": h.changed_by, "reason": h.reason}


def policy_detail(session: Session, p: Policy, today, renewal_status_fn) -> dict:
    applicant = session.get(Applicant, p.applicant_id)
    cov = session.get(CoverageOption, p.coverage_id)
    out = policy_summary(p, applicant)
    out.update({
        "coverage_name": cov.name if cov else None, "snapshot": p.snapshot, "issued_at": p.issued_at,
        "cancellation_reason": p.cancellation_reason, "overlap_reason": p.overlap_reason,
        "status_history": [history_dict(h) for h in session.scalars(
            select(PolicyStatusHistory).where(PolicyStatusHistory.policy_id == p.policy_id)
            .order_by(PolicyStatusHistory.history_id))],
        "endorsements": [endorsement_dict(e) for e in session.scalars(
            select(Endorsement).where(Endorsement.policy_id == p.policy_id).order_by(Endorsement.endorsement_id))],
        "renewals": [renewal_dict(r) for r in session.scalars(
            select(Renewal).where(Renewal.policy_id == p.policy_id).order_by(Renewal.renewal_id))],
        "payments": [payment_dict(x) for x in session.scalars(
            select(Payment).where(Payment.policy_id == p.policy_id).order_by(Payment.payment_id))],
        "renewal_eligibility": renewal_status_fn(session, p, today),
    })
    return out
