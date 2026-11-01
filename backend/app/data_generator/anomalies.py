"""Labelled anomaly injection (SEPARATE from baseline generation; switchable via GenConfig.anomalies).

Each anomaly touches ONE targeted record (or adds ONE new record) drawn from disjoint pools, and writes a
ground-truth label. Labels are evaluation-only and never read by engines or the detector."""
from __future__ import annotations
import copy
from datetime import date, datetime, time, timedelta

from sqlalchemy import insert, select, text

from app.core import rules_config as R
from app.core.errors import DomainError
from app.core.security import Actor
from app.data_generator.config import AS_OF
from app.engines.premium_engine import calculate_premium
from app.models import Endorsement, Payment, Policy, Quote, QuoteAcceptance, Renewal, Applicant
from app.services import ids
from app.services import workflow as W

SEVERITY = {"POLICY_WITHOUT_ACCEPTANCE": "HIGH", "PREMIUM_FORMULA_MISMATCH": "HIGH",
            "ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT": "HIGH", "RENEWAL_FOR_CANCELLED_POLICY": "HIGH",
            "UNAUTHORIZED_POLICY_OVERLAP": "HIGH", "INVALID_FOREIGN_KEY": "CRITICAL",
            "DUPLICATE_TRANSACTION": "MEDIUM", "INVALID_DATE_SEQUENCE": "MEDIUM"}
EXPECTED = {
    "POLICY_WITHOUT_ACCEPTANCE": "Policy must not exist without a recorded customer acceptance",
    "PREMIUM_FORMULA_MISMATCH": "Recorded premium must equal the independently recalculated premium (tolerance 0.01)",
    "ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT": "Endorsement beyond the product coverage limit must be rejected, not approved",
    "RENEWAL_FOR_CANCELLED_POLICY": "No renewal offer may exist for a cancelled policy",
    "UNAUTHORIZED_POLICY_OVERLAP": "Overlapping periods on the same asset/product require a permitted justification",
    "INVALID_FOREIGN_KEY": "Every foreign key must reference an existing parent record",
    "DUPLICATE_TRANSACTION": "A quote/renewal may have at most one successful payment",
    "INVALID_DATE_SEQUENCE": "Acceptance must not precede quote creation",
}


def inject(gen) -> None:
    """gen: pipeline.Generator (provides session, rng, labels, helpers)."""
    s, cfg = gen.s, gen.cfg
    r = gen.rng("anomalies")
    n, nx = cfg.n_core, cfg.n_extra

    def lab(kind, entity, rid):
        gen.label(kind, entity, rid, EXPECTED[kind], "ANOMALY", SEVERITY[kind])

    all_pols = [p for p in s.scalars(select(Policy).order_by(Policy.policy_id))]
    renewed = {x.policy_id for x in s.scalars(select(Renewal))}
    # candidate pool: any quote-path, non-cancelled policy (modifying one record does not affect the others)
    pool = [p for p in all_pols if p.quote_id and p.status != "CANCELLED"]
    r.shuffle(pool)
    used: set[str] = set()

    # 0 UNAUTHORIZED_POLICY_OVERLAP is injected first because it needs complete, clean base policies
    made = 0
    for base in list(pool):
        if made >= n:
            break
        pol = _overlap(gen, r, base, lab)
        if pol:
            made += 1
            used.add(base.policy_id)
    if made < n:
        gen.notes.append(f"overlap injection produced {made}/{n}")
    gen.overlap_made = made
    pool = [p for p in pool if p.policy_id not in used]
    need = n * 2 + nx * 2 + int(n * 0.7)
    if len(pool) < need:
        gen.notes.append(f"anomaly pool short: have {len(pool)} need {need}")
    take = lambda k: [pool.pop() for _ in range(min(k, len(pool)))]      # noqa: E731

    # 1 POLICY_WITHOUT_ACCEPTANCE: acceptance record removed from an otherwise valid policy
    for p in take(n):
        acc = s.scalars(select(QuoteAcceptance).where(QuoteAcceptance.quote_id == p.quote_id)).first()
        s.delete(acc)
        lab("POLICY_WITHOUT_ACCEPTANCE", "Policy", p.policy_id)
    s.flush()

    # 2 PREMIUM_FORMULA_MISMATCH: premium diverges from the formula (policy-level and quote-level)
    n_pol = int(n * 0.7)
    for p in take(n_pol):
        new = round(float(p.premium) * r.choice([r.uniform(1.06, 1.25), r.uniform(0.75, 0.92)]), 2)
        q = s.get(Quote, p.quote_id)
        q.premium = new
        p.premium = new
        for pay in s.scalars(select(Payment).where(Payment.quote_id == p.quote_id, Payment.status == "SUCCESS")):
            pay.amount = new
        lab("PREMIUM_FORMULA_MISMATCH", "Policy", p.policy_id)
    qpool = [q for q in s.scalars(select(Quote).where(Quote.status.in_(("APPROVED", "REFERRED"))).order_by(Quote.quote_id))
             if q.premium is not None]
    r.shuffle(qpool)
    for q in qpool[:n - n_pol]:
        q.premium = round(float(q.premium) * r.uniform(1.07, 1.3), 2)
        lab("PREMIUM_FORMULA_MISMATCH", "Quote", q.quote_id)
    s.flush()

    # 3 ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT: an APPROVED endorsement beyond the coverage option maximum
    for p in take(n):
        snap = p.snapshot
        opt = R.COVERAGE_BY_CODE[snap["coverage_code"]]
        cov_after = int(opt["max_limit"] * r.uniform(1.1, 1.5))
        eff = p.start_date + timedelta(days=r.randint(20, 150))
        prem = calculate_premium(snap["product_key"], **{**snap["premium_breakdown"]["inputs"], "coverage_amount": cov_after})
        when = datetime.combine(eff, time(10, r.randint(0, 59)))
        s.add(Endorsement(endorsement_id=ids.endorsement_id(s, p.policy_id), policy_id=p.policy_id,
                          endorsement_type="COVERAGE_ADJUSTMENT", requested_changes={"new_coverage_amount": cov_after},
                          coverage_before=p.coverage_amount, coverage_after=cov_after,
                          declared_value_before=snap["asset"]["declared_value"], declared_value_after=round(cov_after * 1.05),
                          premium_before=p.premium, premium_after=prem["final_premium"], status="APPROVED",
                          effective_date=eff, policy_snapshot=snap, requested_by="analyst-01", requested_at=when,
                          decided_by="analyst-01", decided_at=when + timedelta(hours=3), decision_reason="Approved"))
        s.flush()
        eid = s.scalars(select(Endorsement.endorsement_id).where(Endorsement.policy_id == p.policy_id)
                        .order_by(Endorsement.endorsement_id.desc())).first()
        lab("ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT", "Endorsement", eid)

    # 4 RENEWAL_FOR_CANCELLED_POLICY: a live renewal offer attached to a cancelled policy
    cancelled = [p for p in all_pols if p.status == "CANCELLED" and p.quote_id and p.policy_id not in renewed]
    r.shuffle(cancelled)
    for p in cancelled[:n]:
        nstart = p.expiry_date + timedelta(days=1)
        gen_at = datetime.combine(p.cancelled_at + timedelta(days=r.randint(1, 20)), time(11, r.randint(0, 59)))
        rid = ids.renewal_id(p.policy_id, nstart.year)
        s.add(Renewal(renewal_id=rid, policy_id=p.policy_id, renewal_year=nstart.year, new_start_date=nstart,
                      new_expiry_date=nstart.replace(year=nstart.year + 1) - timedelta(days=1),
                      coverage_amount=p.coverage_amount, offered_premium=p.premium, premium_breakdown=None,
                      risk_score=None, eligibility_status="ELIGIBLE", reasons=["Eligible for renewal"],
                      status="OFFERED", generated_at=gen_at))
        lab("RENEWAL_FOR_CANCELLED_POLICY", "Renewal", rid)
    if len(cancelled) < n:
        gen.notes.append(f"cancelled-policy pool short: {len(cancelled)} < {n}")
    s.flush()

    # extras (SQLite-safe)
    # 6 INVALID_DATE_SEQUENCE: acceptance timestamp before quote creation
    for p in take(nx):
        acc = s.scalars(select(QuoteAcceptance).where(QuoteAcceptance.quote_id == p.quote_id)).first()
        q = s.get(Quote, p.quote_id)
        acc.accepted_at = q.created_at - timedelta(days=r.randint(1, 5))
        lab("INVALID_DATE_SEQUENCE", "QuoteAcceptance", acc.acceptance_id)
    # 7 DUPLICATE_TRANSACTION: second SUCCESS payment for the same quote
    for p in take(nx):
        pay = s.scalars(select(Payment).where(Payment.quote_id == p.quote_id, Payment.status == "SUCCESS")
                        .order_by(Payment.payment_id)).first()
        dup = Payment(payment_id=ids.payment_id(s), quote_id=pay.quote_id, policy_id=pay.policy_id, amount=pay.amount,
                      status="SUCCESS", method="DEMO", is_demo=True, idempotency_key=None, created_at=pay.created_at)
        s.add(dup)
        lab("DUPLICATE_TRANSACTION", "Payment", dup.payment_id)
    s.flush()
    # 8 INVALID_FOREIGN_KEY: payment referencing a non-existent policy (FK enforcement lifted for this insert only)
    if nx:
        if s.get_bind().dialect.name != "sqlite":
            gen.notes.append("INVALID_FOREIGN_KEY injection skipped: requires disabling FK enforcement (SQLite only)")
        else:
            s.commit()
            conn = s.connection()
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            for i in range(nx):
                pid = ids.payment_id(s)
                s.execute(insert(Payment.__table__).values(
                    payment_id=pid, quote_id=None, policy_id=f"POL-2026-9{i + 1:05d}", renewal_id=None, amount=100.0,
                    status="SUCCESS", method="DEMO", is_demo=True, idempotency_key=None,
                    created_at=datetime.combine(AS_OF, time(3, i))))
                lab("INVALID_FOREIGN_KEY", "Payment", pid)
            s.commit()
            s.connection().exec_driver_sql("PRAGMA foreign_keys=ON")
    s.commit()


def _overlap(gen, r, base: Policy, lab):
    """Second policy on the SAME asset/product with an overlapping term and no permitted reason."""
    s = gen.s
    q0 = s.get(Quote, base.quote_id)
    app_ = s.get(Applicant, base.applicant_id)
    actor = Actor(f"cust-ovl-{base.applicant_id}", "CUSTOMER", app_.owner_key)
    start = base.start_date + timedelta(days=r.randint(30, 200))
    if start > AS_OF - timedelta(days=1):
        return None
    now = datetime.combine(start, time(9, r.randint(0, 59)))
    same_asset = s.scalars(select(Policy).where(Policy.asset_id == base.asset_id)).all()
    try:
        q2 = W.submit_application(s, copy.deepcopy(q0.input_snapshot), actor, now)
        if q2.status == "REFERRED":
            cur = W.current_decision(s, q2.quote_id)
            W.review_quote(s, q2.quote_id, "APPROVE", gen.staff(cur.approval_authority, r), "Reviewed", now + timedelta(hours=2))
        if q2.status != "APPROVED":
            return None
        q2.asset_id = base.asset_id
        s.flush()
        W.accept_quote(s, q2.quote_id, actor, now + timedelta(hours=3))
        for p in same_asset:                                     # let the workflow guard pass for this injection only
            p.overlap_reason = "__injection_guard__"
        _, pol, _ = W.demo_payment(s, q2.quote_id, "SUCCESS", actor, f"ovl-{q2.quote_id}", now + timedelta(hours=4))
    except DomainError as e:
        gen.notes.append(f"overlap injection skipped for {base.policy_id}: {e.message}")
        return None
    finally:
        for p in same_asset:
            p.overlap_reason = None
        s.flush()
    lab("UNAUTHORIZED_POLICY_OVERLAP", "Policy", pol.policy_id)
    return pol
