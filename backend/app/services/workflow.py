"""Quote -> decision -> acceptance -> payment -> policy -> endorsement -> renewal workflow.

This is the SINGLE service layer used by both the customer portal API and the operations
API (and later by the synthetic data generator). All timestamps are injectable (`now`) so
generation is deterministic. All state changes append history/audit rows.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import rules_config as R
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailed
from app.core.security import SYSTEM, Actor, assert_can_access_applicant, require_staff
from app.engines.common import is_missing
from app.engines.eligibility_engine import evaluate_eligibility
from app.engines.policy_engine import (can_transition, check_endorsement_limits, check_issuance_prerequisites,
                                       check_renewal_eligibility, compute_expiry, find_unauthorized_overlaps)
from app.engines.premium_engine import calculate_premium
from app.engines.risk_engine import assess_risk
from app.engines.underwriting_engine import coverage_authority, decide, role_can_act
from app.models import (Applicant, AuditEvent, CoverageOption, Endorsement, InsuredAsset, Payment, Policy,
                        PolicyCoverage, PolicyStatusHistory, Product, Quote, QuoteAcceptance, QuoteCoverage,
                        Renewal, RiskAssessment, UnderwritingDecision)
from app.services import ids


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _get(session: Session, model, pk, label: str):
    obj = session.get(model, pk)
    if obj is None:
        raise NotFoundError(f"{label} {pk} not found")
    return obj


def audit(session, entity_type, entity_id, event_type, actor: Actor, payload=None, now=None):
    session.add(AuditEvent(audit_id=ids.audit_id(session), entity_type=entity_type, entity_id=entity_id,
                           event_type=event_type, actor=actor.user_id, actor_role=actor.role,
                           payload=payload, occurred_at=now or utcnow()))


# ------------------------------------------------------------------ context
def _normalise_attributes(attrs: dict) -> dict:
    out = {}
    for k, v in (attrs or {}).items():
        if isinstance(v, str):
            v = v.strip()
            if v == "":
                v = None
        if v is not None and k in R.ENUM_FIELDS:
            v = str(v).upper()
        if v is not None and k in R.INT_FIELDS:
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValidationFailed(f"{k} must be a whole number")
            if v < 0:
                raise ValidationFailed(f"{k} must not be negative")
        out[k] = v
    return out


def _num(v, name):
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValidationFailed(f"{name} must be a number")
    if f < 0:
        raise ValidationFailed(f"{name} must not be negative")
    return f


def build_context(product_key, applicant_age, location, declared_value, attributes, coverage_code,
                  requested_coverage, as_of_year=R.AS_OF_YEAR) -> dict:
    cfg = R.PRODUCTS[product_key]
    attrs = dict(attributes or {})
    ctx = {**attrs, "applicant_age": applicant_age, "declared_value": declared_value,
           "requested_coverage": requested_coverage, "coverage_code": coverage_code, "location": location}
    yf = cfg.get("age_field")
    ctx["asset_age_years"] = (max(0, as_of_year - int(attrs[yf]))
                              if yf and not is_missing(attrs.get(yf)) else None)
    ctx["location_tier"] = (R.LOCATION_RISK_TIER.get(location, R.DEFAULT_LOCATION_TIER)
                            if not is_missing(location) else None)
    return ctx


def _ctx_for(quote_or_snap_applicant_age, asset, coverage_code, requested, product_key, as_of_year):
    return build_context(product_key, quote_or_snap_applicant_age, asset.location,
                         float(asset.declared_value) if asset.declared_value is not None else None,
                         asset.attributes, coverage_code, requested, as_of_year)


# -------------------------------------------------------------- submission
def submit_application(session: Session, payload: dict, actor: Actor, now: datetime | None = None) -> Quote:
    """Persist applicant + asset + quote and run the full deterministic evaluation."""
    now = now or utcnow()
    pk = str(payload.get("product_key", "")).upper()
    if pk not in R.PRODUCTS:
        raise ValidationFailed(f"Unknown product_key '{payload.get('product_key')}'")
    ap, asset_in = payload.get("applicant") or {}, payload.get("asset") or {}
    if is_missing(ap.get("full_name")):
        raise ValidationFailed("applicant.full_name is required")
    age = ap.get("age")
    if age is not None and age != "":
        try:
            age = int(age)
        except (TypeError, ValueError):
            raise ValidationFailed("applicant.age must be a whole number")
        if not 0 < age < 120:
            raise ValidationFailed("applicant.age out of range")
    else:
        age = None
    owner_key = actor.customer_key if actor.role == "CUSTOMER" else payload.get("owner_key")
    email = (ap.get("email") or "").strip().lower() or None

    applicant = None
    if email:
        applicant = session.scalars(select(Applicant).where(Applicant.email == email,
                                                            Applicant.owner_key == owner_key)).first()
    if applicant is None:
        applicant = Applicant(applicant_id=ids.applicant_id(session), owner_key=owner_key,
                              full_name=ap["full_name"].strip(), email=email, phone=ap.get("phone"),
                              age=age, applicant_type=ap.get("applicant_type", "INDIVIDUAL"),
                              location=ap.get("location"), status="ACTIVE", created_at=now)
        session.add(applicant)
        session.flush()
        audit(session, "Applicant", applicant.applicant_id, "APPLICANT_CREATED", actor, None, now)
    else:
        applicant.age = age if age is not None else applicant.age

    product = session.scalars(select(Product).where(Product.product_key == pk)).one()
    attrs = _normalise_attributes(asset_in.get("attributes"))
    if pk == "PROPERTY" and is_missing(attrs.get("year_built")) and not is_missing(attrs.get("property_age_years")):
        attrs["year_built"] = R.AS_OF_YEAR - int(attrs["property_age_years"])
    asset = InsuredAsset(asset_id=ids.asset_id(session), applicant_id=applicant.applicant_id,
                         asset_type=R.PRODUCTS[pk]["asset_type"], declared_value=_num(asset_in.get("declared_value"), "declared_value"),
                         location=asset_in.get("location"), attributes=attrs, status="ACTIVE", created_at=now)
    session.add(asset)
    session.flush()

    code = payload.get("coverage_code")
    cov = session.scalars(select(CoverageOption).where(CoverageOption.code == code)).first() if code else None
    requested = _num(payload.get("requested_coverage"), "requested_coverage")
    quote = Quote(quote_id=ids.quote_id(session), applicant_id=applicant.applicant_id, asset_id=asset.asset_id,
                  product_id=product.product_id, coverage_id=cov.coverage_id if cov else None,
                  coverage_code=code, requested_coverage=requested, status="REFERRED",
                  input_snapshot={"applicant": {**ap, "age": age}, "asset": {**asset_in, "attributes": attrs},
                                  "product_key": pk, "coverage_code": code, "requested_coverage": requested},
                  rules_version=R.RULES_VERSION, valid_until=(now + timedelta(days=R.QUOTE_VALIDITY_DAYS)).date(),
                  created_at=now)
    session.add(quote)
    session.flush()
    audit(session, "Quote", quote.quote_id, "QUOTE_SUBMITTED", actor,
          {"product": pk, "applicant_id": applicant.applicant_id, "asset_id": asset.asset_id}, now)
    if cov is not None and requested is not None:
        session.add(QuoteCoverage(quote_id=quote.quote_id, coverage_id=cov.coverage_id, requested_amount=requested))
    evaluate_quote(session, quote, applicant, asset, pk, actor, now)
    return quote


def evaluate_quote(session, quote: Quote, applicant: Applicant, asset: InsuredAsset, pk: str,
                   actor: Actor, now: datetime) -> UnderwritingDecision:
    ctx = _ctx_for(applicant.age, asset, quote.coverage_code,
                   float(quote.requested_coverage) if quote.requested_coverage is not None else None,
                   pk, R.AS_OF_YEAR)
    elig = evaluate_eligibility(pk, ctx)
    risk = assess_risk(pk, ctx)
    premium = None
    if elig.status == "ELIGIBLE":
        premium = calculate_premium(pk, coverage_amount=ctx["requested_coverage"], coverage_code=ctx["coverage_code"],
                                    asset_age_years=ctx["asset_age_years"], location_tier=ctx["location_tier"],
                                    prior_claims=ctx.get("previous_claims"), risk_category=risk.category)
    dec = decide(pk, elig, risk, ctx)

    session.add(RiskAssessment(assessment_id=ids.assessment_id(session), quote_id=quote.quote_id,
                               score=risk.score, category=risk.category, factors=risk.factors,
                               missing_info=risk.missing_info, explanation=risk.explanation,
                               rules_version=risk.rules_version, assessed_at=now))
    quote.eligibility_status = elig.status
    quote.eligibility_detail = elig.to_dict()
    quote.risk_score, quote.risk_category = risk.score, risk.category
    quote.premium = premium["final_premium"] if premium else None
    quote.premium_breakdown = premium
    quote.status = dec["outcome"]
    audit(session, "Quote", quote.quote_id, "ELIGIBILITY_EVALUATED", actor, {"status": elig.status}, now)
    audit(session, "Quote", quote.quote_id, "RISK_ASSESSED", actor, {"score": risk.score, "category": risk.category}, now)
    if premium:
        audit(session, "Quote", quote.quote_id, "PREMIUM_CALCULATED", actor,
              {"final": premium["final_premium"], "formula": premium["formula_version"]}, now)
    return _add_decision(session, quote, dec, "AUTOMATED", "SYSTEM", "SYSTEM", None, now)


def _add_decision(session, quote, dec: dict, dtype, by, role, notes, now) -> UnderwritingDecision:
    seq = (session.scalars(select(UnderwritingDecision.sequence).where(UnderwritingDecision.quote_id == quote.quote_id)
                           .order_by(UnderwritingDecision.sequence.desc())).first() or 0) + 1
    d = UnderwritingDecision(decision_id=ids.decision_id(session), quote_id=quote.quote_id, sequence=seq,
                             outcome=dec["outcome"], decision_type=dtype, risk_score=dec["risk_score"],
                             reasons=dec["reasons"], rule_ids=dec["rule_ids"],
                             approval_authority=dec["approval_authority"], decided_by=by, decided_role=role,
                             notes=notes, decided_at=now, rule_engine_version=dec["engine_version"])
    session.add(d)
    session.flush()
    audit(session, "Quote", quote.quote_id, "UNDERWRITING_DECISION", Actor(by, role),
          {"decision_id": d.decision_id, "outcome": d.outcome, "authority": d.approval_authority,
           "rule_ids": d.rule_ids, "type": dtype}, now)
    return d


def current_decision(session, quote_id: str) -> UnderwritingDecision | None:
    return session.scalars(select(UnderwritingDecision).where(UnderwritingDecision.quote_id == quote_id)
                           .order_by(UnderwritingDecision.sequence.desc())).first()


def _quote_for(session, quote_id, actor) -> tuple[Quote, Applicant]:
    quote = _get(session, Quote, quote_id, "Quote")
    applicant = _get(session, Applicant, quote.applicant_id, "Applicant")
    assert_can_access_applicant(actor, applicant)
    return quote, applicant


# ---------------------------------------------------- information resubmission
def provide_information(session, quote_id, updates: dict, actor: Actor, now=None) -> Quote:
    """Customer/analyst supplies missing info for a PENDING_INFORMATION quote -> re-evaluated
    as a NEW decision (history kept; before/after recorded in the audit trail)."""
    now = now or utcnow()
    quote, applicant = _quote_for(session, quote_id, actor)
    if quote.status != "PENDING_INFORMATION":
        raise ConflictError("Quote is not awaiting information")
    asset = _get(session, InsuredAsset, quote.asset_id, "Asset")
    before = {"attributes": dict(asset.attributes or {}), "declared_value": float(asset.declared_value or 0)}
    new_attrs = {**(asset.attributes or {}), **_normalise_attributes(updates.get("attributes"))}
    if R.PRODUCT_BY_ID[quote.product_id] == "PROPERTY" and is_missing(new_attrs.get("year_built")) \
            and not is_missing(new_attrs.get("property_age_years")):          # same derivation as submit_application
        new_attrs["year_built"] = R.AS_OF_YEAR - int(new_attrs["property_age_years"])
    asset.attributes = new_attrs
    if updates.get("declared_value") is not None:
        asset.declared_value = _num(updates["declared_value"], "declared_value")
    if updates.get("location"):
        asset.location = updates["location"]
    session.flush()
    audit(session, "Quote", quote.quote_id, "INFORMATION_PROVIDED", actor,
          {"before": before, "after": {"attributes": new_attrs}}, now)
    pk = R.PRODUCT_BY_ID[quote.product_id]
    evaluate_quote(session, quote, applicant, asset, pk, actor, now)
    return quote


# ------------------------------------------------------------ manual review
def review_quote(session, quote_id, action, actor: Actor, notes=None, now=None) -> UnderwritingDecision:
    now = now or utcnow()
    require_staff(actor)
    quote = _get(session, Quote, quote_id, "Quote")
    cur = current_decision(session, quote_id)
    if action not in ("APPROVE", "REJECT", "REQUEST_INFORMATION"):
        raise ValidationFailed("action must be APPROVE, REJECT or REQUEST_INFORMATION")
    if cur is None or cur.outcome != "REFERRED":
        raise ConflictError("Only quotes in REFERRED status can be manually reviewed")
    if action in ("APPROVE", "REJECT") and not role_can_act(actor.role, cur.approval_authority):
        raise ForbiddenError(f"Role {actor.role} lacks authority; {cur.approval_authority} required")
    outcome = {"APPROVE": "APPROVED", "REJECT": "DECLINED", "REQUEST_INFORMATION": "PENDING_INFORMATION"}[action]
    rid = {"APPROVE": "UW-MAN-APR", "REJECT": "UW-MAN-REJ", "REQUEST_INFORMATION": "UW-MAN-INF"}[action]
    dec = {"outcome": outcome, "approval_authority": cur.approval_authority, "risk_score": cur.risk_score,
           "reasons": [{"rule_id": rid, "message": f"{action} by {actor.user_id} ({actor.role})"
                                                    + (f": {notes}" if notes else "")}],
           "rule_ids": [rid], "engine_version": R.UW_ENGINE_VERSION}
    quote.status = outcome
    return _add_decision(session, quote, dec, "MANUAL", actor.user_id, actor.role, notes, now)


# ------------------------------------------------- acceptance / payment / issue
def accept_quote(session, quote_id, actor: Actor, now=None) -> QuoteAcceptance:
    now = now or utcnow()
    quote, _ = _quote_for(session, quote_id, actor)
    if session.scalars(select(QuoteAcceptance).where(QuoteAcceptance.quote_id == quote_id)).first():
        raise ConflictError("Quote has already been accepted")
    cur = current_decision(session, quote_id)
    if quote.status != "APPROVED" or cur is None or cur.outcome != "APPROVED":
        raise ConflictError(f"Only APPROVED quotes can be accepted (status: {quote.status})")
    if now.date() > quote.valid_until:
        raise ConflictError("Quote has expired")
    acc = QuoteAcceptance(acceptance_id=ids.acceptance_id(session), quote_id=quote_id, accepted_by=actor.user_id,
                          accepted_at=now, terms_version=R.TERMS_VERSION)
    session.add(acc)
    quote.status = "ACCEPTED"
    session.flush()
    audit(session, "Quote", quote_id, "QUOTE_ACCEPTED", actor, {"acceptance_id": acc.acceptance_id}, now)
    return acc


def demo_payment(session, quote_id, outcome, actor: Actor, idempotency_key=None, now=None):
    """DEMO PAYMENT ONLY - no real payment processing. Returns (payment, policy|None, duplicate)."""
    now = now or utcnow()
    quote, _ = _quote_for(session, quote_id, actor)
    if idempotency_key:
        ex = session.scalars(select(Payment).where(Payment.idempotency_key == idempotency_key)).first()
        if ex:
            pol = session.scalars(select(Policy).where(Policy.quote_id == quote_id)).first()
            return ex, pol, True
    if outcome not in ("SUCCESS", "FAILED", "PENDING"):
        raise ValidationFailed("outcome must be SUCCESS, FAILED or PENDING")
    if quote.status != "ACCEPTED":
        raise ConflictError(f"Payment requires an ACCEPTED quote (status: {quote.status})")
    if session.scalars(select(Payment).where(Payment.quote_id == quote_id, Payment.status == "PENDING")).first():
        raise ConflictError("A pending payment exists for this quote; resolve it first")
    pay = Payment(payment_id=ids.payment_id(session), quote_id=quote_id, amount=quote.premium, status=outcome,
                  method="DEMO", is_demo=True, idempotency_key=idempotency_key, created_at=now)
    session.add(pay)
    session.flush()
    audit(session, "Payment", pay.payment_id, "DEMO_PAYMENT_" + outcome, actor,
          {"quote_id": quote_id, "amount": float(quote.premium)}, now)
    pol = issue_policy(session, quote_id, actor, now) if outcome == "SUCCESS" else None
    return pay, pol, False


def resolve_pending_payment(session, payment_id, outcome, actor: Actor, now=None):
    now = now or utcnow()
    pay = _get(session, Payment, payment_id, "Payment")
    quote, _ = _quote_for(session, pay.quote_id, actor)
    if pay.status != "PENDING":
        raise ConflictError("Only PENDING payments can be resolved")
    if outcome not in ("SUCCESS", "FAILED"):
        raise ValidationFailed("outcome must be SUCCESS or FAILED")
    pay.status = outcome
    audit(session, "Payment", payment_id, "DEMO_PAYMENT_RESOLVED_" + outcome, actor, None, now)
    pol = issue_policy(session, pay.quote_id, actor, now) if outcome == "SUCCESS" else None
    return pay, pol


def _policy_dict(p: Policy) -> dict:
    return {"policy_id": p.policy_id, "asset_id": p.asset_id, "product_id": p.product_id,
            "start_date": p.start_date, "expiry_date": p.expiry_date, "status": p.status,
            "cancelled_on": p.cancelled_at, "overlap_reason": p.overlap_reason,
            "renewal_of_policy_id": p.renewal_of_policy_id}


def _transition(session, policy: Policy, to: str, actor: Actor, reason: str | None, now):
    if not can_transition(policy.status, to):
        raise ConflictError(f"Invalid policy transition {policy.status} -> {to}")
    session.add(PolicyStatusHistory(policy_id=policy.policy_id, from_status=policy.status, to_status=to,
                                    changed_at=now, changed_by=actor.user_id, reason=reason))
    policy.status = to
    session.flush()


def issue_policy(session, quote_id, actor: Actor, now=None, start_date: date | None = None) -> Policy:
    now = now or utcnow()
    quote, applicant = _quote_for(session, quote_id, actor)
    acc = session.scalars(select(QuoteAcceptance).where(QuoteAcceptance.quote_id == quote_id)).first()
    pay = session.scalars(select(Payment).where(Payment.quote_id == quote_id)
                          .order_by(Payment.created_at.desc(), Payment.payment_id.desc())).first()
    cur = current_decision(session, quote_id)
    start = start_date or now.date()
    expiry = compute_expiry(start)
    blocking = []
    asset_policies = session.scalars(select(Policy).where(Policy.asset_id == quote.asset_id,
                                                          Policy.product_id == quote.product_id)).all()
    cand = {"policy_id": "~NEW~", "asset_id": quote.asset_id, "product_id": quote.product_id,
            "start_date": start, "expiry_date": expiry, "status": "ACTIVE", "cancelled_on": None,
            "overlap_reason": None, "renewal_of_policy_id": None}
    if find_unauthorized_overlaps([cand] + [_policy_dict(p) for p in asset_policies]):
        blocking.append("UNAUTHORIZED_POLICY_OVERLAP: asset already has an overlapping policy period")
    if session.scalars(select(Policy).where(Policy.quote_id == quote_id)).first():
        blocking.append("DUPLICATE_ISSUANCE: policy already issued for this quote")
    fails = check_issuance_prerequisites(
        quote_status=quote.status, eligibility_status=quote.eligibility_status,
        decision_outcome=cur.outcome if cur else None, acceptance_recorded=acc is not None,
        payment_status=pay.status if pay else None, payment_amount=pay.amount if pay else None,
        premium=quote.premium, blocking_exceptions=blocking)
    if fails:
        raise ConflictError("Policy issuance prerequisites not met", fails)

    pk = R.PRODUCT_BY_ID[quote.product_id]
    asset = _get(session, InsuredAsset, quote.asset_id, "Asset")
    policy = Policy(policy_id=ids.policy_id(session), quote_id=quote_id, applicant_id=quote.applicant_id,
                    asset_id=quote.asset_id, product_id=quote.product_id, coverage_id=quote.coverage_id,
                    coverage_amount=quote.requested_coverage, premium=quote.premium, status="ACTIVE",
                    start_date=start, expiry_date=expiry, issued_at=now,
                    snapshot={"quote_id": quote_id, "product_key": pk, "coverage_code": quote.coverage_code,
                              "coverage_amount": float(quote.requested_coverage), "premium": float(quote.premium),
                              "premium_breakdown": quote.premium_breakdown, "risk_score": quote.risk_score,
                              "risk_category": quote.risk_category,
                              "applicant": {"applicant_id": applicant.applicant_id, "full_name": applicant.full_name,
                                            "age": applicant.age},
                              "asset": {"asset_id": asset.asset_id, "declared_value": float(asset.declared_value),
                                        "location": asset.location, "attributes": asset.attributes},
                              "decision_id": cur.decision_id, "acceptance_id": acc.acceptance_id,
                              "payment_id": pay.payment_id, "rules_version": R.RULES_VERSION})
    session.add(policy)
    session.flush()
    session.add(PolicyCoverage(policy_id=policy.policy_id, coverage_id=quote.coverage_id,
                               limit_amount=quote.requested_coverage))
    session.add(PolicyStatusHistory(policy_id=policy.policy_id, from_status=None, to_status="ACTIVE",
                                    changed_at=now, changed_by=actor.user_id,
                                    reason="Issued: approved, accepted and payment satisfied"))
    pay.policy_id = policy.policy_id
    quote.status = "POLICY_ISSUED"
    session.flush()
    audit(session, "Policy", policy.policy_id, "POLICY_ISSUED", actor, {"quote_id": quote_id}, now)
    return policy


def cancel_policy(session, policy_id, reason, actor: Actor, now=None, effective: date | None = None) -> Policy:
    now = now or utcnow()
    policy = _get(session, Policy, policy_id, "Policy")
    assert_can_access_applicant(actor, _get(session, Applicant, policy.applicant_id, "Applicant"))
    if is_missing(reason):
        raise ValidationFailed("A cancellation reason is required")
    _transition(session, policy, "CANCELLED", actor, reason, now)
    policy.cancelled_at = effective or now.date()
    policy.cancellation_reason = reason
    for r in session.scalars(select(Renewal).where(Renewal.policy_id == policy_id,
                                                   Renewal.status.in_(("GENERATED", "OFFERED")))):
        r.status, r.responded_at, r.response_reason = "CANCELLED", now, "Policy cancelled"
    audit(session, "Policy", policy_id, "POLICY_CANCELLED", actor, {"reason": reason}, now)
    return policy


def expire_policies(session, today: date, actor: Actor = SYSTEM, now=None) -> int:
    now = now or utcnow()
    n = 0
    for p in session.scalars(select(Policy).where(Policy.status == "ACTIVE", Policy.expiry_date < today)):
        _transition(session, p, "EXPIRED", actor, "Term ended", now)
        audit(session, "Policy", p.policy_id, "POLICY_EXPIRED", actor, None, now)
        n += 1
    return n


# ---------------------------------------------------------------- endorsements
def effective_terms(session, policy: Policy) -> tuple[float, float]:
    """(coverage, declared_value) after the latest APPROVED endorsement; originals are never overwritten."""
    e = session.scalars(select(Endorsement).where(Endorsement.policy_id == policy.policy_id,
                                                  Endorsement.status == "APPROVED")
                        .order_by(Endorsement.endorsement_id.desc())).first()
    if e:
        return float(e.coverage_after), float(e.declared_value_after)
    return float(policy.coverage_amount), float(policy.snapshot["asset"]["declared_value"])


def request_endorsement(session, policy_id, change: dict, effective_date: date, actor: Actor, now=None) -> Endorsement:
    now = now or utcnow()
    policy = _get(session, Policy, policy_id, "Policy")
    assert_can_access_applicant(actor, _get(session, Applicant, policy.applicant_id, "Applicant"))
    if policy.status != "ACTIVE":
        raise ConflictError(f"Endorsements require an ACTIVE policy (status: {policy.status})")
    etype = change.get("endorsement_type")
    from app.core.enums import ENDORSEMENT_TYPES
    if etype not in ENDORSEMENT_TYPES:
        raise ValidationFailed(f"endorsement_type must be one of {ENDORSEMENT_TYPES}")
    if not (policy.start_date <= effective_date <= policy.expiry_date):
        raise ValidationFailed("effective_date must fall within the policy period")
    cov_before, dv_before = effective_terms(session, policy)
    cov_after = _num(change.get("new_coverage_amount"), "new_coverage_amount") or cov_before
    dv_after = _num(change.get("new_declared_value"), "new_declared_value") or dv_before
    snap = policy.snapshot
    pk = snap["product_key"]
    violations = check_endorsement_limits(pk, snap["coverage_code"], cov_after, dv_after)
    prem_before = float(policy.premium)
    prem_after = None
    if not violations:
        inputs = dict(snap["premium_breakdown"]["inputs"])
        inputs["coverage_amount"] = cov_after
        prem_after = calculate_premium(pk, **inputs)["final_premium"]
    e = Endorsement(endorsement_id=ids.endorsement_id(session, policy_id), policy_id=policy_id,
                    endorsement_type=etype, requested_changes=change, coverage_before=cov_before,
                    coverage_after=cov_after, declared_value_before=dv_before, declared_value_after=dv_after,
                    premium_before=prem_before, premium_after=prem_after,
                    status="REJECTED" if violations else "PENDING", effective_date=effective_date,
                    policy_snapshot=snap, requested_by=actor.user_id, requested_at=now,
                    decided_by="SYSTEM" if violations else None, decided_at=now if violations else None,
                    decision_reason="; ".join(violations) if violations else None)
    session.add(e)
    session.flush()
    audit(session, "Endorsement", e.endorsement_id, "ENDORSEMENT_REQUESTED" if not violations else "ENDORSEMENT_AUTO_REJECTED",
          actor, {"policy_id": policy_id, "violations": violations}, now)
    return e


def decide_endorsement(session, endorsement_id, approve: bool, actor: Actor, reason=None, now=None) -> Endorsement:
    now = now or utcnow()
    require_staff(actor)
    e = _get(session, Endorsement, endorsement_id, "Endorsement")
    if e.status != "PENDING":
        raise ConflictError("Only PENDING endorsements can be decided")
    pk = e.policy_snapshot["product_key"]
    required = coverage_authority(pk, float(e.coverage_after))
    if approve and not role_can_act(actor.role, required):
        raise ForbiddenError(f"Role {actor.role} lacks authority; {required} required for this coverage amount")
    e.status = "APPROVED" if approve else "REJECTED"
    e.decided_by, e.decided_at, e.decision_reason = actor.user_id, now, reason
    audit(session, "Endorsement", endorsement_id, "ENDORSEMENT_" + e.status, actor, {"reason": reason}, now)
    return e


# -------------------------------------------------------------------- renewals
def generate_renewal(session, policy_id, actor: Actor, today: date, now=None) -> Renewal:
    now = now or utcnow()
    policy = _get(session, Policy, policy_id, "Policy")
    assert_can_access_applicant(actor, _get(session, Applicant, policy.applicant_id, "Applicant"))
    new_start = policy.expiry_date + timedelta(days=1)
    year = new_start.year
    rid = ids.renewal_id(policy_id, year)
    existing = session.get(Renewal, rid)
    blocking, _ = check_renewal_eligibility(
        policy_status=policy.status, expiry_date=policy.expiry_date, today=today,
        has_cancellation=policy.cancelled_at is not None, pending_payments=0,
        existing_open_renewal=existing is not None)
    if blocking:
        raise ConflictError("Renewal cannot be generated", blocking)

    snap = policy.snapshot
    pk = snap["product_key"]
    cov, dv = effective_terms(session, policy)
    applicant = _get(session, Applicant, policy.applicant_id, "Applicant")
    asset = _get(session, InsuredAsset, policy.asset_id, "Asset")
    ctx = build_context(pk, applicant.age, asset.location, dv, asset.attributes, snap["coverage_code"], cov, year)
    elig = evaluate_eligibility(pk, ctx)
    risk = assess_risk(pk, ctx)
    reasons, premium = [], None
    if elig.status != "ELIGIBLE":
        reasons.append(f"Renewal eligibility: {elig.status}")
    if risk.score >= R.DECLINE_RISK_SCORE:
        reasons.append(f"Risk score {risk.score} at/above decline threshold {R.DECLINE_RISK_SCORE}")
    if session.scalars(select(Payment).where(Payment.policy_id == policy_id, Payment.status == "PENDING")).first():
        reasons.append("Outstanding pending payment")
    if elig.status == "ELIGIBLE":
        premium = calculate_premium(pk, coverage_amount=cov, coverage_code=snap["coverage_code"],
                                    asset_age_years=ctx["asset_age_years"], location_tier=ctx["location_tier"],
                                    prior_claims=ctx.get("previous_claims"), risk_category=risk.category)
    ok = not reasons
    ren = Renewal(renewal_id=rid, policy_id=policy_id, renewal_year=year, new_start_date=new_start,
                  new_expiry_date=compute_expiry(new_start), coverage_amount=cov,
                  offered_premium=premium["final_premium"] if premium and ok else None,
                  premium_breakdown=premium if ok else None, risk_score=risk.score,
                  eligibility_status=elig.status, reasons=reasons or ["Eligible for renewal"],
                  status="OFFERED" if ok else "CANCELLED", generated_at=now,
                  response_reason=None if ok else "; ".join(reasons))
    session.add(ren)
    session.flush()
    audit(session, "Renewal", rid, "RENEWAL_OFFERED" if ok else "RENEWAL_WITHHELD", actor,
          {"policy_id": policy_id, "reasons": ren.reasons}, now)
    return ren


def respond_renewal(session, renewal_id, accept: bool, actor: Actor, payment_outcome="SUCCESS",
                    reason=None, now=None):
    """Customer accepts (with DEMO payment) or declines. Returns (renewal, new_policy|None)."""
    now = now or utcnow()
    ren = _get(session, Renewal, renewal_id, "Renewal")
    policy = _get(session, Policy, ren.policy_id, "Policy")
    applicant = _get(session, Applicant, policy.applicant_id, "Applicant")
    assert_can_access_applicant(actor, applicant)
    if ren.status != "OFFERED":
        raise ConflictError(f"Renewal is {ren.status}; only OFFERED renewals can be answered")
    if not accept:
        ren.status, ren.responded_at, ren.response_reason = "DECLINED", now, reason
        audit(session, "Renewal", renewal_id, "RENEWAL_DECLINED", actor, {"reason": reason}, now)
        return ren, None
    if payment_outcome not in ("SUCCESS", "FAILED", "PENDING"):
        raise ValidationFailed("payment_outcome must be SUCCESS, FAILED or PENDING")
    pay = Payment(payment_id=ids.payment_id(session), quote_id=None, policy_id=policy.policy_id,
                  renewal_id=renewal_id, amount=ren.offered_premium, status=payment_outcome, method="DEMO",
                  is_demo=True, created_at=now)
    session.add(pay)
    session.flush()
    if payment_outcome != "SUCCESS":
        audit(session, "Payment", pay.payment_id, "DEMO_PAYMENT_" + payment_outcome, actor, {"renewal_id": renewal_id}, now)
        return ren, None
    snap = dict(policy.snapshot)
    new_pol = Policy(policy_id=ids.policy_id(session), quote_id=None, applicant_id=policy.applicant_id,
                     asset_id=policy.asset_id, product_id=policy.product_id, coverage_id=policy.coverage_id,
                     coverage_amount=ren.coverage_amount, premium=ren.offered_premium, status="ACTIVE",
                     start_date=ren.new_start_date, expiry_date=ren.new_expiry_date, issued_at=now,
                     renewal_of_policy_id=policy.policy_id,
                     snapshot={**snap, "coverage_amount": float(ren.coverage_amount),
                               "premium": float(ren.offered_premium), "premium_breakdown": ren.premium_breakdown,
                               "renewal_id": renewal_id, "renewal_of": policy.policy_id,
                               "asset": {**snap["asset"], "declared_value": effective_terms(session, policy)[1]}})
    session.add(new_pol)
    session.flush()
    session.add(PolicyCoverage(policy_id=new_pol.policy_id, coverage_id=policy.coverage_id,
                               limit_amount=ren.coverage_amount))
    session.add(PolicyStatusHistory(policy_id=new_pol.policy_id, from_status=None, to_status="ACTIVE",
                                    changed_at=now, changed_by=actor.user_id, reason=f"Renewal {renewal_id}"))
    pay.policy_id = new_pol.policy_id
    _transition(session, policy, "RENEWED", actor, f"Renewed by {new_pol.policy_id}", now)
    ren.status, ren.responded_at, ren.new_policy_id = "ACCEPTED", now, new_pol.policy_id
    audit(session, "Renewal", renewal_id, "RENEWAL_ACCEPTED", actor, {"new_policy_id": new_pol.policy_id}, now)
    return ren, new_pol


# ------------------------------------------------ additions used by the API / generator
def review_decision(session, decision_id, action, actor: Actor, notes=None, now=None) -> UnderwritingDecision:
    """Review addressed by decision ID: refuses if that decision has already been superseded."""
    d = _get(session, UnderwritingDecision, decision_id, "Decision")
    cur = current_decision(session, d.quote_id)
    if cur.decision_id != decision_id:
        raise ConflictError("This decision has been superseded by a newer one; reload the quote")
    return review_quote(session, d.quote_id, action, actor, notes, now)


def reevaluate_quote(session, quote_id, actor: Actor, now=None) -> Quote:
    """Staff re-run of the deterministic evaluation (appends a new decision; history kept)."""
    now = now or utcnow()
    require_staff(actor)
    quote = _get(session, Quote, quote_id, "Quote")
    if quote.status in ("ACCEPTED", "POLICY_ISSUED"):
        raise ConflictError(f"Quote in status {quote.status} cannot be re-evaluated")
    applicant = _get(session, Applicant, quote.applicant_id, "Applicant")
    asset = _get(session, InsuredAsset, quote.asset_id, "Asset")
    evaluate_quote(session, quote, applicant, asset, R.PRODUCT_BY_ID[quote.product_id], actor, now)
    return quote


def expire_stale_renewals(session, today: date, actor: Actor = SYSTEM, now=None) -> int:
    """OFFERED renewals whose new term has already started without a response -> EXPIRED."""
    now = now or utcnow()
    n = 0
    for r in session.scalars(select(Renewal).where(Renewal.status == "OFFERED", Renewal.new_start_date < today)
                             .order_by(Renewal.renewal_id)):
        r.status, r.responded_at, r.response_reason = "EXPIRED", now, "No response before new term start"
        audit(session, "Renewal", r.renewal_id, "RENEWAL_EXPIRED", actor, None, now)
        n += 1
    return n


def renewal_status_for_policy(session, policy: Policy, today: date) -> dict:
    """Read-only renewal eligibility view (delegates to the policy engine)."""
    year = (policy.expiry_date + timedelta(days=1)).year
    existing = session.get(Renewal, ids.renewal_id(policy.policy_id, year))
    blocking, _ = check_renewal_eligibility(
        policy_status=policy.status, expiry_date=policy.expiry_date, today=today,
        has_cancellation=policy.cancelled_at is not None, pending_payments=0,
        existing_open_renewal=existing is not None)
    return {"eligible": not blocking, "reasons": blocking,
            "window_start": policy.expiry_date - timedelta(days=R.RENEWAL_WINDOW_DAYS),
            "window_end": policy.expiry_date, "renewal_id": existing.renewal_id if existing else None}
