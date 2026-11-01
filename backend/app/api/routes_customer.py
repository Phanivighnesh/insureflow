"""Customer portal API. Every route delegates to services.workflow; ownership is enforced up-front
and foreign records return 404 (no existence leak)."""
from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api import serializers as S
from app.api.deps import TransactionalRoute, customer_only, get_db
from app.core import rules_config as R
from app.core.errors import ForbiddenError, NotFoundError
from app.core.security import Actor, assert_can_access_applicant
from app.models import Applicant, Payment, Policy, Quote, Renewal
from app.schemas import requests as Q
from app.services import workflow as W
from app.services.demo_scenarios import SCENARIOS

router = APIRouter(prefix="/api/customer", tags=["customer"], route_class=TransactionalRoute)


def _own(session, model, pk, label, actor):
    obj = session.get(model, pk)
    if obj is None:
        raise NotFoundError(f"{label} {pk} not found")
    owner = obj if isinstance(obj, Applicant) else session.get(Applicant, obj.applicant_id)
    try:
        assert_can_access_applicant(actor, owner)
    except ForbiddenError:
        raise NotFoundError(f"{label} {pk} not found")
    return obj


def _today():
    return W.utcnow().date()


# ---- public discovery (no auth)
@router.get("/products")
def products():
    out = []
    for key, p in R.PRODUCTS.items():
        out.append({"product_key": key, "product_id": p["product_id"], "name": p["name"],
                    "coverage_options": [{k: c[k] for k in ("coverage_id", "code", "name", "min_limit", "max_limit")}
                                         for c in R.COVERAGE_OPTIONS if c["product_key"] == key],
                    "eligibility": {"applicant_age": p["applicant_age"], "insured_value": p["insured_value"],
                                    "max_asset_age": p["max_asset_age"], "allowed_values": p["allowed_values"],
                                    "max_coverage_to_value_ratio": R.MAX_COVERAGE_TO_VALUE_RATIO},
                    "asset_fields": R.ASSET_FORM_FIELDS[key], "locations": sorted(R.LOCATION_RISK_TIER),
                    "auto_approval_limit": p["auto_approval_limit"]})
    return {"products": out, "currency": R.CURRENCY, "rules_version": R.RULES_VERSION,
            "demo_notice": "DEMO ENVIRONMENT - illustrative synthetic rules"}


@router.get("/demo-scenarios")
def demo_scenarios():
    """Prefilled INPUTS only. Submit one to POST /customer/quotes; the backend produces the outcome."""
    return {"scenarios": [{"id": s["id"], "title": s["title"], "intent": s["intent"], "payload": s["payload"]}
                          for s in SCENARIOS]}


# ---- quotes
@router.post("/quotes", status_code=201)
def submit_quote(body: Q.QuoteRequest, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    q = W.submit_application(db, body.model_dump(), actor)
    return S.quote_detail(db, q, for_customer=True)


@router.get("/quotes")
def list_quotes(page: int = 1, page_size: int = 20, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    stmt = (select(Quote, Applicant).join(Applicant, Applicant.applicant_id == Quote.applicant_id)
            .where(Applicant.owner_key == actor.customer_key).order_by(Quote.quote_id.desc()))
    return S.paginate(db, stmt, page, page_size, lambda q, a: S.quote_summary(q, a, None, True))


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: str, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    return S.quote_detail(db, _own(db, Quote, quote_id, "Quote", actor), for_customer=True)


@router.post("/quotes/{quote_id}/information")
def provide_info(quote_id: str, body: Q.InformationUpdate, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    _own(db, Quote, quote_id, "Quote", actor)
    q = W.provide_information(db, quote_id, body.model_dump(), actor)
    return S.quote_detail(db, q, True)


@router.post("/quotes/{quote_id}/accept")
def accept(quote_id: str, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    q = _own(db, Quote, quote_id, "Quote", actor)
    acc = W.accept_quote(db, quote_id, actor)
    return {"acceptance_id": acc.acceptance_id, "accepted_at": acc.accepted_at, "quote": S.quote_detail(db, q, True)}


@router.post("/quotes/{quote_id}/payment")
def pay(quote_id: str, body: Q.PaymentRequest, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    """DEMO PAYMENT - no real payment processing."""
    q = _own(db, Quote, quote_id, "Quote", actor)
    pay_, pol, dup = W.demo_payment(db, quote_id, body.outcome, actor, body.idempotency_key)
    return {"demo_payment": True, "duplicate_request": dup, "payment": S.payment_dict(pay_),
            "policy": S.policy_summary(pol) if pol else None, "quote": S.quote_detail(db, q, True)}


@router.post("/payments/{payment_id}/resolve")
def resolve(payment_id: str, body: Q.ResolvePayment, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    p = db.get(Payment, payment_id)
    if p is None or p.quote_id is None:
        raise NotFoundError(f"Payment {payment_id} not found")
    _own(db, Quote, p.quote_id, "Payment", actor)
    pay_, pol = W.resolve_pending_payment(db, payment_id, body.outcome, actor)
    return {"payment": S.payment_dict(pay_), "policy": S.policy_summary(pol) if pol else None}


# ---- policies
@router.get("/policies")
def list_policies(page: int = 1, page_size: int = 20, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    stmt = (select(Policy, Applicant).join(Applicant, Applicant.applicant_id == Policy.applicant_id)
            .where(Applicant.owner_key == actor.customer_key).order_by(Policy.policy_id.desc()))
    return S.paginate(db, stmt, page, page_size, S.policy_summary)


@router.get("/policies/{policy_id}")
def get_policy(policy_id: str, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    p = _own(db, Policy, policy_id, "Policy", actor)
    return S.policy_detail(db, p, _today(), W.renewal_status_for_policy)


@router.post("/policies/{policy_id}/cancel")
def cancel(policy_id: str, body: Q.CancelRequest, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    p = _own(db, Policy, policy_id, "Policy", actor)
    W.cancel_policy(db, policy_id, body.reason, actor)
    return S.policy_detail(db, p, _today(), W.renewal_status_for_policy)


@router.post("/policies/{policy_id}/endorsements", status_code=201)
def endorse(policy_id: str, body: Q.EndorsementRequest, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    _own(db, Policy, policy_id, "Policy", actor)
    change = {"endorsement_type": body.endorsement_type, "new_coverage_amount": body.new_coverage_amount,
              "new_declared_value": body.new_declared_value, "changes": body.changes}
    return S.endorsement_dict(W.request_endorsement(db, policy_id, change, body.effective_date, actor))


@router.post("/policies/{policy_id}/renewals", status_code=201)
def request_renewal(policy_id: str, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    p = _own(db, Policy, policy_id, "Policy", actor)
    return S.renewal_dict(W.generate_renewal(db, policy_id, actor, _today()), p)


# ---- renewals
@router.get("/renewals")
def list_renewals(page: int = 1, page_size: int = 20, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    stmt = (select(Renewal, Policy).join(Policy, Policy.policy_id == Renewal.policy_id)
            .join(Applicant, Applicant.applicant_id == Policy.applicant_id)
            .where(Applicant.owner_key == actor.customer_key).order_by(Renewal.renewal_id.desc()))
    return S.paginate(db, stmt, page, page_size, lambda r, p: S.renewal_dict(r, p))


def _own_renewal(db, rid, actor):
    r = db.get(Renewal, rid)
    if r is None:
        raise NotFoundError(f"Renewal {rid} not found")
    _own(db, Policy, r.policy_id, "Renewal", actor)
    return r


@router.post("/renewals/{renewal_id}/accept")
def accept_renewal(renewal_id: str, body: Q.RenewalAccept, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    _own_renewal(db, renewal_id, actor)
    ren, new = W.respond_renewal(db, renewal_id, True, actor, body.payment_outcome)
    return {"demo_payment": True, "renewal": S.renewal_dict(ren), "new_policy": S.policy_summary(new) if new else None}


@router.post("/renewals/{renewal_id}/decline")
def decline_renewal(renewal_id: str, body: Q.RenewalDecline, actor: Actor = Depends(customer_only), db=Depends(get_db)):
    _own_renewal(db, renewal_id, actor)
    ren, _ = W.respond_renewal(db, renewal_id, False, actor, reason=body.reason)
    return {"renewal": S.renewal_dict(ren)}
