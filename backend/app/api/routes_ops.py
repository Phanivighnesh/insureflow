"""Operations dashboard API (staff roles). Same workflow service as the customer portal."""
from __future__ import annotations
from collections import Counter
from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select

from app.api import serializers as S
from app.api.deps import TransactionalRoute, get_db, staff_only
from app.core import rules_config as R
from app.core.errors import NotFoundError, ValidationFailed
from app.core.security import Actor
from app.engines.underwriting_engine import role_can_act
from app.models import (Applicant, AuditEvent, DetectedException, Endorsement, InsuredAsset, Payment, Policy,
                        Quote, Renewal, UnderwritingDecision, ValidationRun)
from app.schemas import requests as Q
from app.services import workflow as W

router = APIRouter(prefix="/api", tags=["operations"], route_class=TransactionalRoute)


def _get(db, model, pk, label):
    o = db.get(model, pk)
    if o is None:
        raise NotFoundError(f"{label} {pk} not found")
    return o


def _latest_run(db):
    return db.scalars(select(ValidationRun).order_by(ValidationRun.run_id.desc())).first()


def _current_decisions(db, quote_ids):
    if not quote_ids:
        return {}
    rows = db.scalars(select(UnderwritingDecision).where(UnderwritingDecision.quote_id.in_(quote_ids))
                      .order_by(UnderwritingDecision.quote_id, UnderwritingDecision.sequence)).all()
    return {d.quote_id: d for d in rows}      # later sequence overwrites earlier


# ------------------------------------------------------------------ dashboards
@router.get("/dashboard/summary")
def dashboard_summary(actor: Actor = Depends(staff_only), db=Depends(get_db)):
    cnt = lambda m, *w: db.scalar(select(func.count()).select_from(m).where(*w))   # noqa: E731
    run = _latest_run(db)
    exc = db.scalar(select(func.count()).select_from(DetectedException).where(
        DetectedException.run_id == run.run_id)) if run else 0
    return {"total_applicants": cnt(Applicant), "total_quotes": cnt(Quote), "issued_policies": cnt(Policy),
            "active_policies": cnt(Policy, Policy.status == "ACTIVE"), "renewals": cnt(Renewal),
            "pending_underwriting_reviews": cnt(Quote, Quote.status == "REFERRED"),
            "approved_applications": cnt(Quote, Quote.status.in_(("APPROVED", "ACCEPTED", "POLICY_ISSUED"))),
            "declined_applications": cnt(Quote, Quote.status == "DECLINED"),
            "pending_information": cnt(Quote, Quote.status == "PENDING_INFORMATION"),
            "exception_count": exc, "last_validation_run": run.run_id if run else None}


@router.get("/dashboard/underwriting")
def dashboard_underwriting(actor: Actor = Depends(staff_only), db=Depends(get_db)):
    latest = (select(UnderwritingDecision.quote_id, func.max(UnderwritingDecision.sequence).label("m"))
              .group_by(UnderwritingDecision.quote_id).subquery())
    dist = db.execute(select(UnderwritingDecision.outcome, func.count()).join(
        latest, and_(UnderwritingDecision.quote_id == latest.c.quote_id, UnderwritingDecision.sequence == latest.c.m))
        .group_by(UnderwritingDecision.outcome)).all()
    prem = [float(p) for (p,) in db.execute(select(Quote.premium).where(Quote.premium.is_not(None)))]
    edges = [0, 500, 1000, 2500, 5000, 10000, 1e12]
    labels = ["<500", "500-999", "1,000-2,499", "2,500-4,999", "5,000-9,999", "10,000+"]
    buckets = [sum(1 for p in prem if edges[i] <= p < edges[i + 1]) for i in range(6)]
    by_product = db.execute(select(Quote.product_id, func.count()).group_by(Quote.product_id)).all()
    by_risk = db.execute(select(Quote.risk_category, func.count()).group_by(Quote.risk_category)).all()
    by_pol = db.execute(select(Policy.status, func.count()).group_by(Policy.status)).all()
    return {"decision_distribution": {k: v for k, v in dist},
            "premium_distribution": [{"bucket": l, "count": c} for l, c in zip(labels, buckets)],
            "average_premium": round(sum(prem) / len(prem), 2) if prem else None,
            "product_volume": {R.PRODUCT_BY_ID[k]: v for k, v in by_product},
            "risk_distribution": {(k or "UNSCORED"): v for k, v in by_risk},
            "policy_lifecycle": {k: v for k, v in by_pol}}


@router.get("/dashboard/renewals")
def dashboard_renewals(actor: Actor = Depends(staff_only), db=Depends(get_db)):
    return {"outcomes": {k: v for k, v in db.execute(select(Renewal.status, func.count()).group_by(Renewal.status))}}


@router.get("/dashboard/exceptions")
def dashboard_exceptions(actor: Actor = Depends(staff_only), db=Depends(get_db)):
    run = _latest_run(db)
    if not run:
        return {"run_id": None, "by_issue_type": {}, "by_severity": {}, "trend": []}
    rows = db.scalars(select(DetectedException).where(DetectedException.run_id == run.run_id)).all()
    trend = Counter((e.record_date.strftime("%Y-%m") if e.record_date else "unknown") for e in rows)
    return {"run_id": run.run_id, "by_issue_type": dict(Counter(e.issue_type for e in rows)),
            "by_severity": dict(Counter(e.severity for e in rows)),
            "by_resolution": dict(Counter(e.resolution_status for e in rows)),
            "trend": [{"month": k, "count": v} for k, v in sorted(trend.items())]}


# ------------------------------------------------------------ applicants/assets
def _like(col_list, q):
    return or_(*[c.ilike(f"%{q}%") for c in col_list])


@router.get("/applicants")
def list_applicants(q: str | None = None, status: str | None = None, location: str | None = None,
                    sort: str = "applicant_id", order: str = "asc", page: int = 1, page_size: int = 25,
                    actor: Actor = Depends(staff_only), db=Depends(get_db)):
    nq = select(func.count()).select_from(Quote).where(Quote.applicant_id == Applicant.applicant_id).scalar_subquery()
    na = select(func.count()).select_from(InsuredAsset).where(InsuredAsset.applicant_id == Applicant.applicant_id).scalar_subquery()
    stmt = select(Applicant, nq, na)
    if q:
        stmt = stmt.where(_like([Applicant.applicant_id, Applicant.full_name, Applicant.email], q))
    if status:
        stmt = stmt.where(Applicant.status == status)
    if location:
        stmt = stmt.where(Applicant.location == location)
    col = {"applicant_id": Applicant.applicant_id, "name": Applicant.full_name, "created_at": Applicant.created_at,
           "location": Applicant.location}.get(sort, Applicant.applicant_id)
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc())
    return S.paginate(db, stmt, page, page_size, lambda a, n_q, n_a: {
        "applicant_id": a.applicant_id, "full_name": a.full_name, "email": a.email, "applicant_type": a.applicant_type,
        "location": a.location, "age": a.age, "status": a.status, "quote_count": n_q, "asset_count": n_a})


@router.get("/applicants/{applicant_id}")
def get_applicant(applicant_id: str, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    a = _get(db, Applicant, applicant_id, "Applicant")
    assets = db.scalars(select(InsuredAsset).where(InsuredAsset.applicant_id == applicant_id)
                        .order_by(InsuredAsset.asset_id)).all()
    quotes = db.scalars(select(Quote).where(Quote.applicant_id == applicant_id).order_by(Quote.quote_id)).all()
    pols = db.scalars(select(Policy).where(Policy.applicant_id == applicant_id).order_by(Policy.policy_id)).all()
    return {"applicant_id": a.applicant_id, "full_name": a.full_name, "email": a.email, "phone": a.phone,
            "age": a.age, "location": a.location, "applicant_type": a.applicant_type, "status": a.status,
            "created_at": a.created_at,
            "assets": [{"asset_id": x.asset_id, "asset_type": x.asset_type, "declared_value": S.f(x.declared_value),
                        "location": x.location, "attributes": x.attributes} for x in assets],
            "quotes": [S.quote_summary(x) for x in quotes], "policies": [S.policy_summary(x) for x in pols]}


@router.get("/assets")
def list_assets(q: str | None = None, asset_type: str | None = None, page: int = 1, page_size: int = 25,
                actor: Actor = Depends(staff_only), db=Depends(get_db)):
    npol = select(func.count()).select_from(Policy).where(Policy.asset_id == InsuredAsset.asset_id).scalar_subquery()
    stmt = select(InsuredAsset, Applicant.full_name, npol).join(Applicant, Applicant.applicant_id == InsuredAsset.applicant_id)
    if q:
        stmt = stmt.where(_like([InsuredAsset.asset_id, Applicant.full_name, InsuredAsset.location], q))
    if asset_type:
        stmt = stmt.where(InsuredAsset.asset_type == asset_type)
    return S.paginate(db, stmt.order_by(InsuredAsset.asset_id), page, page_size, lambda x, owner, n: {
        "asset_id": x.asset_id, "applicant_id": x.applicant_id, "owner": owner, "asset_type": x.asset_type,
        "declared_value": S.f(x.declared_value), "location": x.location, "attributes": x.attributes,
        "policy_count": n})


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    x = _get(db, InsuredAsset, asset_id, "Asset")
    pols = db.scalars(select(Policy).where(Policy.asset_id == asset_id).order_by(Policy.policy_id)).all()
    return {"asset_id": x.asset_id, "applicant_id": x.applicant_id, "asset_type": x.asset_type,
            "declared_value": S.f(x.declared_value), "location": x.location, "attributes": x.attributes,
            "policies": [S.policy_summary(p) for p in pols],
            "quotes": [S.quote_summary(q) for q in db.scalars(select(Quote).where(Quote.asset_id == asset_id))]}


# ----------------------------------------------------------------------- quotes
@router.get("/quotes")
def list_quotes(q: str | None = None, status: str | None = None, product: str | None = None,
                risk_category: str | None = None, page: int = 1, page_size: int = 25,
                actor: Actor = Depends(staff_only), db=Depends(get_db)):
    stmt = select(Quote, Applicant).join(Applicant, Applicant.applicant_id == Quote.applicant_id)
    if q:
        stmt = stmt.where(_like([Quote.quote_id, Applicant.full_name, Applicant.email, Applicant.applicant_id], q))
    if status:
        stmt = stmt.where(Quote.status == status)
    if product:
        stmt = stmt.where(Quote.product_id == R.PRODUCTS[product.upper()]["product_id"]) if product.upper() in R.PRODUCTS else stmt
    if risk_category:
        stmt = stmt.where(Quote.risk_category == risk_category)
    res = S.paginate(db, stmt.order_by(Quote.quote_id.desc()), page, page_size, lambda qq, a: (qq, a))
    cur = _current_decisions(db, [qq.quote_id for qq, _ in res["items"]])
    res["items"] = [S.quote_summary(qq, a, cur.get(qq.quote_id)) for qq, a in res["items"]]
    return res


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: str, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    return S.quote_detail(db, _get(db, Quote, quote_id, "Quote"))


@router.post("/quotes/{quote_id}/evaluate")
def evaluate(quote_id: str, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    return S.quote_detail(db, W.reevaluate_quote(db, quote_id, actor))


def _audit_ids(db, quote_id):
    q = _get(db, Quote, quote_id, "Quote")
    ids_ = {quote_id}
    pol = db.scalars(select(Policy).where(Policy.quote_id == quote_id)).first()
    ids_ |= {p.payment_id for p in db.scalars(select(Payment).where(Payment.quote_id == quote_id))}
    if pol:
        ids_.add(pol.policy_id)
        ids_ |= {e.endorsement_id for e in db.scalars(select(Endorsement).where(Endorsement.policy_id == pol.policy_id))}
        ids_ |= {r.renewal_id for r in db.scalars(select(Renewal).where(Renewal.policy_id == pol.policy_id))}
    ids_.add(q.applicant_id)
    return ids_


@router.get("/quotes/{quote_id}/audit")
def quote_audit(quote_id: str, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    ev = db.scalars(select(AuditEvent).where(AuditEvent.entity_id.in_(_audit_ids(db, quote_id)))
                    .order_by(AuditEvent.occurred_at, AuditEvent.audit_id)).all()
    return {"quote_id": quote_id, "events": [S.audit_dict(a) for a in ev]}


@router.get("/audit")
def audit_log(entity_id: str | None = None, entity_type: str | None = None, event_type: str | None = None,
              page: int = 1, page_size: int = 50, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    stmt = select(AuditEvent)
    for col, v in ((AuditEvent.entity_id, entity_id), (AuditEvent.entity_type, entity_type), (AuditEvent.event_type, event_type)):
        if v:
            stmt = stmt.where(col == v)
    return S.paginate(db, stmt.order_by(AuditEvent.audit_id.desc()), page, page_size, S.audit_dict)


# ------------------------------------------------------------------ underwriting
@router.get("/underwriting/pending")
def pending(include_pending_information: bool = False, page: int = 1, page_size: int = 25,
            actor: Actor = Depends(staff_only), db=Depends(get_db)):
    statuses = ("REFERRED", "PENDING_INFORMATION") if include_pending_information else ("REFERRED",)
    stmt = (select(Quote, Applicant).join(Applicant, Applicant.applicant_id == Quote.applicant_id)
            .where(Quote.status.in_(statuses)).order_by(Quote.created_at, Quote.quote_id))
    res = S.paginate(db, stmt, page, page_size, lambda qq, a: (qq, a))
    cur = _current_decisions(db, [qq.quote_id for qq, _ in res["items"]])
    items = []
    for qq, a in res["items"]:
        d = cur[qq.quote_id]
        row = S.quote_summary(qq, a, d)
        row.update({"decision_id": d.decision_id, "referral_reasons": d.reasons,
                    "can_act": d.outcome == "REFERRED" and role_can_act(actor.role, d.approval_authority)})
        items.append(row)
    res["items"] = items
    return res


@router.get("/underwriting/decisions")
def decisions(quote_id: str | None = None, outcome: str | None = None, page: int = 1, page_size: int = 50,
              actor: Actor = Depends(staff_only), db=Depends(get_db)):
    stmt = select(UnderwritingDecision)
    if quote_id:
        stmt = stmt.where(UnderwritingDecision.quote_id == quote_id)
    if outcome:
        stmt = stmt.where(UnderwritingDecision.outcome == outcome)
    return S.paginate(db, stmt.order_by(UnderwritingDecision.decision_id.desc()), page, page_size, S.decision_dict)


def _review(action):
    def route(decision_id: str, body: Q.ReviewRequest, actor: Actor = Depends(staff_only), db=Depends(get_db)):
        d = W.review_decision(db, decision_id, action, actor, body.notes)
        return {"decision": S.decision_dict(d), "quote": S.quote_detail(db, db.get(Quote, d.quote_id))}
    return route


for _path, _act in (("approve", "APPROVE"), ("reject", "REJECT"), ("request-information", "REQUEST_INFORMATION")):
    router.add_api_route(f"/underwriting/{{decision_id}}/{_path}", _review(_act), methods=["POST"])


# ---------------------------------------------------------------------- policies
@router.get("/policies")
def list_policies(q: str | None = None, status: str | None = None, product: str | None = None,
                  page: int = 1, page_size: int = 25, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    stmt = select(Policy, Applicant).join(Applicant, Applicant.applicant_id == Policy.applicant_id)
    if q:
        stmt = stmt.where(_like([Policy.policy_id, Applicant.full_name, Applicant.applicant_id, Policy.asset_id], q))
    if status:
        stmt = stmt.where(Policy.status == status)
    if product and product.upper() in R.PRODUCTS:
        stmt = stmt.where(Policy.product_id == R.PRODUCTS[product.upper()]["product_id"])
    return S.paginate(db, stmt.order_by(Policy.policy_id.desc()), page, page_size, S.policy_summary)


@router.get("/policies/{policy_id}")
def get_policy(policy_id: str, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    return S.policy_detail(db, _get(db, Policy, policy_id, "Policy"), W.utcnow().date(), W.renewal_status_for_policy)


@router.post("/policies/{policy_id}/cancel")
def cancel(policy_id: str, body: Q.CancelRequest, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    p = W.cancel_policy(db, policy_id, body.reason, actor)
    return S.policy_detail(db, p, W.utcnow().date(), W.renewal_status_for_policy)


# ------------------------------------------------------------------ endorsements
@router.get("/endorsements")
def list_endorsements(policy_id: str | None = None, status: str | None = None, page: int = 1, page_size: int = 25,
                      actor: Actor = Depends(staff_only), db=Depends(get_db)):
    stmt = select(Endorsement)
    if policy_id:
        stmt = stmt.where(Endorsement.policy_id == policy_id)
    if status:
        stmt = stmt.where(Endorsement.status == status)
    return S.paginate(db, stmt.order_by(Endorsement.endorsement_id.desc()), page, page_size, S.endorsement_dict)


@router.post("/endorsements", status_code=201)
def create_endorsement(policy_id: str, body: Q.EndorsementRequest, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    change = {"endorsement_type": body.endorsement_type, "new_coverage_amount": body.new_coverage_amount,
              "new_declared_value": body.new_declared_value, "changes": body.changes}
    return S.endorsement_dict(W.request_endorsement(db, policy_id, change, body.effective_date, actor))


@router.post("/endorsements/{endorsement_id}/approve")
def approve_endorsement(endorsement_id: str, body: Q.DecideEndorsement, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    return S.endorsement_dict(W.decide_endorsement(db, endorsement_id, True, actor, body.reason))


@router.post("/endorsements/{endorsement_id}/reject")
def reject_endorsement(endorsement_id: str, body: Q.DecideEndorsement, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    return S.endorsement_dict(W.decide_endorsement(db, endorsement_id, False, actor, body.reason))


# ---------------------------------------------------------------------- renewals
@router.get("/renewals")
def list_renewals(status: str | None = None, policy_id: str | None = None, page: int = 1, page_size: int = 25,
                  actor: Actor = Depends(staff_only), db=Depends(get_db)):
    stmt = select(Renewal, Policy).join(Policy, Policy.policy_id == Renewal.policy_id)
    if status:
        stmt = stmt.where(Renewal.status == status)
    if policy_id:
        stmt = stmt.where(Renewal.policy_id == policy_id)
    return S.paginate(db, stmt.order_by(Renewal.renewal_id.desc()), page, page_size, lambda r, p: S.renewal_dict(r, p))


@router.post("/renewals/generate", status_code=201)
def generate_renewal(body: Q.RenewalGenerate, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    p = _get(db, Policy, body.policy_id, "Policy")
    return S.renewal_dict(W.generate_renewal(db, body.policy_id, actor, body.as_of_date or W.utcnow().date()), p)


@router.post("/renewals/{renewal_id}/accept")
def accept_renewal(renewal_id: str, body: Q.RenewalAccept, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    ren, new = W.respond_renewal(db, renewal_id, True, actor, body.payment_outcome)
    return {"renewal": S.renewal_dict(ren), "new_policy": S.policy_summary(new) if new else None}


@router.post("/renewals/{renewal_id}/decline")
def decline_renewal(renewal_id: str, body: Q.RenewalDecline, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    ren, _ = W.respond_renewal(db, renewal_id, False, actor, reason=body.reason)
    return {"renewal": S.renewal_dict(ren)}


# --------------------------------------------------------------------- exceptions
def _exc_dict(e: DetectedException) -> dict:
    return {"exception_id": e.exception_id, "run_id": e.run_id, "issue_type": e.issue_type,
            "affected_entity": e.affected_entity, "affected_record_id": e.affected_record_id,
            "severity": e.severity, "record_date": e.record_date, "detected_at": e.detected_at,
            "expected_outcome": e.expected_outcome, "actual_outcome": e.actual_outcome, "details": e.details,
            "resolution_status": e.resolution_status, "resolution_note": e.resolution_note,
            "resolved_by": e.resolved_by}


@router.get("/exceptions")
def list_exceptions(issue_type: str | None = None, severity: str | None = None, resolution_status: str | None = None,
                    run_id: str | None = None, page: int = 1, page_size: int = 25,
                    actor: Actor = Depends(staff_only), db=Depends(get_db)):
    run = run_id or (lambda r: r.run_id if r else None)(_latest_run(db))
    stmt = select(DetectedException).where(DetectedException.run_id == run)
    for col, v in ((DetectedException.issue_type, issue_type), (DetectedException.severity, severity),
                   (DetectedException.resolution_status, resolution_status)):
        if v:
            stmt = stmt.where(col == v)
    return S.paginate(db, stmt.order_by(DetectedException.exception_id), page, page_size, _exc_dict)


@router.get("/exceptions/{exception_id}")
def get_exception(exception_id: str, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    return _exc_dict(_get(db, DetectedException, exception_id, "Exception"))


@router.post("/exceptions/{exception_id}/resolution")
def resolve_exception(exception_id: str, body: Q.ResolveException, actor: Actor = Depends(staff_only), db=Depends(get_db)):
    e = _get(db, DetectedException, exception_id, "Exception")
    if body.resolution_status == "RESOLVED" and not body.note:
        raise ValidationFailed("A resolution note is required to mark an exception RESOLVED")
    e.resolution_status, e.resolution_note, e.resolved_by = body.resolution_status, body.note, actor.user_id
    W.audit(db, "Exception", exception_id, "EXCEPTION_" + body.resolution_status, actor, {"note": body.note})
    return _exc_dict(e)
