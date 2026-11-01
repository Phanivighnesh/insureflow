"""Independent data-quality / anomaly detector.

Reads ONLY business tables. It must never import or query GroundTruth - detection is evaluated against
ground truth elsewhere (services/evaluation.py). Every finding is derived from business rules."""
from __future__ import annotations
from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func, select

from app.core import enums as E
from app.core import rules_config as R
from app.database.base import Base
from app.engines.policy_engine import can_transition, check_endorsement_limits, find_unauthorized_overlaps
from app.engines.premium_engine import premium_matches, recalculate_from_snapshot
from app.models import (Applicant, DetectedException, Endorsement, Payment, Policy, PolicyStatusHistory, Quote,
                        QuoteAcceptance, Renewal, UnderwritingDecision)

NON_DATASET = {"ground_truth", "detected_exceptions", "validation_runs", "dataset_runs", "alembic_version", "ai_interactions"}
TABLE_ENTITY = {"applicants": "Applicant", "insured_assets": "InsuredAsset", "quotes": "Quote", "policies": "Policy",
                "payments": "Payment", "endorsements": "Endorsement", "renewals": "Renewal",
                "underwriting_decisions": "UnderwritingDecision", "risk_assessments": "RiskAssessment",
                "quote_acceptances": "QuoteAcceptance", "policy_status_history": "PolicyStatusHistory",
                "quote_coverages": "QuoteCoverage", "policy_coverages": "PolicyCoverage", "risk_factors": "RiskFactor",
                "product_coverages": "ProductCoverage", "approval_authorities": "ApprovalAuthority",
                "products": "Product", "coverage_options": "CoverageOption", "audit_events": "AuditEvent"}
SEVERITY = {"INVALID_FOREIGN_KEY": "CRITICAL", "POLICY_WITHOUT_ACCEPTANCE": "HIGH", "POLICY_WITHOUT_PAYMENT": "HIGH",
            "POLICY_WITHOUT_APPROVAL": "HIGH", "POLICY_WITHOUT_ORIGIN": "HIGH", "PREMIUM_FORMULA_MISMATCH": "HIGH",
            "ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT": "HIGH", "RENEWAL_FOR_CANCELLED_POLICY": "HIGH",
            "UNAUTHORIZED_POLICY_OVERLAP": "HIGH", "LIFECYCLE_VIOLATION": "HIGH", "POLICY_COVERAGE_LIMIT_VIOLATION": "HIGH",
            "INELIGIBLE_QUOTE_PROGRESSED": "HIGH", "DUPLICATE_TRANSACTION": "MEDIUM", "INVALID_DATE_SEQUENCE": "MEDIUM",
            "INVALID_ENUM_VALUE": "MEDIUM", "DUPLICATE_APPLICANT": "LOW"}
EXPECTED = {
    "INVALID_FOREIGN_KEY": "Every foreign key references an existing parent record",
    "POLICY_WITHOUT_ACCEPTANCE": "Policy issuance requires a recorded customer acceptance",
    "POLICY_WITHOUT_PAYMENT": "Policy issuance requires a successful payment", "POLICY_WITHOUT_APPROVAL": "Policy issuance requires current APPROVED underwriting decision",
    "POLICY_WITHOUT_ORIGIN": "Policy must originate from a quote or an accepted renewal",
    "PREMIUM_FORMULA_MISMATCH": "Recorded premium equals independently recalculated premium within tolerance",
    "ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT": "Approved endorsements stay within product coverage limits",
    "RENEWAL_FOR_CANCELLED_POLICY": "Cancelled policies have no live renewal offer",
    "UNAUTHORIZED_POLICY_OVERLAP": "Overlapping policy periods on one asset/product need a permitted reason",
    "LIFECYCLE_VIOLATION": "Policy status history follows valid lifecycle transitions and ends at current status",
    "POLICY_COVERAGE_LIMIT_VIOLATION": "Policy coverage is within the coverage option limits",
    "INELIGIBLE_QUOTE_PROGRESSED": "Only ELIGIBLE quotes progress past underwriting", "DUPLICATE_TRANSACTION": "At most one successful payment per quote/renewal",
    "INVALID_DATE_SEQUENCE": "Dates follow the business sequence", "INVALID_ENUM_VALUE": "Enumerated fields hold allowed values",
    "DUPLICATE_APPLICANT": "No duplicate applicant (same email and owner)"}


class Report:
    def __init__(self):
        self.findings: list[dict] = []
        self.checks: dict[str, dict] = {}
        self._seen: set = set()

    def check(self, name, checked, failed):
        self.checks[name] = {"checked": checked, "failed": failed}

    def add(self, issue_type, entity, rid, actual, record_date=None, details=None):
        key = (issue_type, rid)
        if key in self._seen:
            return
        self._seen.add(key)
        self.findings.append({"issue_type": issue_type, "affected_entity": entity, "affected_record_id": rid,
                              "severity": SEVERITY.get(issue_type, "MEDIUM"), "record_date": record_date,
                              "expected_outcome": EXPECTED.get(issue_type, ""), "actual_outcome": actual,
                              "details": details or {}})


def _d(x):
    return x.date() if hasattr(x, "date") and callable(x.date) else x


def run_validation(session) -> Report:
    rep = Report()
    _fk(session, rep); _enums(session, rep); _duplicates(session, rep); _dates(session, rep)
    _lifecycle(session, rep); _premiums(session, rep); _limits(session, rep); _issuance(session, rep)
    _renewals(session, rep); _overlaps(session, rep); _progression(session, rep)
    rep.findings.sort(key=lambda f: (f["issue_type"], f["affected_record_id"]))
    return rep


def dataset_tables():
    return [t for t in Base.metadata.sorted_tables if t.name not in NON_DATASET]


def _fk(session, rep):
    checked = failed = 0
    for t in dataset_tables():
        for fk in t.foreign_keys:
            parent = fk.column.table.alias("p") if fk.column.table is t else fk.column.table
            pcol = parent.c[fk.column.name]
            child = t.c[fk.parent.name]
            pks = [c for c in t.primary_key.columns]
            stmt = (select(*pks).select_from(t.outerjoin(parent, child == pcol))
                    .where(child.is_not(None), pcol.is_(None)))
            n = session.scalar(select(func.count()).select_from(t).where(child.is_not(None)))
            checked += n
            for row in session.execute(stmt):
                failed += 1
                rid = "|".join(str(v) for v in row)
                rep.add("INVALID_FOREIGN_KEY", TABLE_ENTITY.get(t.name, t.name), rid,
                        f"{t.name}.{fk.parent.name} references missing {fk.column.table.name}.{fk.column.name}",
                        details={"column": fk.parent.name, "parent_table": fk.column.table.name})
    rep.check("foreign_key_integrity", checked, failed)


def _enums(session, rep):
    spec = [(Quote, "status", E.QUOTE_STATUSES, "quote_id"), (Policy, "status", E.POLICY_STATUSES, "policy_id"),
            (Renewal, "status", E.RENEWAL_STATUSES, "renewal_id"), (Endorsement, "status", E.ENDORSEMENT_STATUSES, "endorsement_id"),
            (Payment, "status", E.PAYMENT_STATUSES, "payment_id"),
            (UnderwritingDecision, "outcome", E.DECISION_OUTCOMES, "decision_id")]
    checked = failed = 0
    for model, col, allowed, pk in spec:
        checked += session.scalar(select(func.count()).select_from(model))
        for rid, val in session.execute(select(getattr(model, pk), getattr(model, col)).where(getattr(model, col).not_in(allowed))):
            failed += 1
            rep.add("INVALID_ENUM_VALUE", model.__name__, rid, f"{col}={val}")
    rep.check("allowed_enumerations", checked, failed)


def _duplicates(session, rep):
    failed = 0
    pays = defaultdict(list)
    for p in session.scalars(select(Payment).where(Payment.status == "SUCCESS").order_by(Payment.payment_id)):
        key = p.quote_id or p.renewal_id
        if key:
            pays[key].append(p)
    for key, lst in pays.items():
        for extra in lst[1:]:
            failed += 1
            rep.add("DUPLICATE_TRANSACTION", "Payment", extra.payment_id, f"{len(lst)} successful payments for {key}",
                    _d(extra.created_at))
    rep.check("duplicate_payments", len(pays), failed)
    seen, dups = {}, 0
    for a in session.scalars(select(Applicant).order_by(Applicant.applicant_id)):
        k = (a.email, a.owner_key)
        if a.email and k in seen:
            dups += 1
            rep.add("DUPLICATE_APPLICANT", "Applicant", a.applicant_id, f"duplicates {seen[k]}", _d(a.created_at))
        seen.setdefault(k, a.applicant_id)
    rep.check("duplicate_applicants", len(seen), dups)


def _dates(session, rep):
    checked = failed = 0
    quotes = {q.quote_id: q for q in session.scalars(select(Quote))}
    for a in session.scalars(select(QuoteAcceptance)):
        q = quotes.get(a.quote_id)
        if q:
            checked += 1
            if a.accepted_at < q.created_at:
                failed += 1
                rep.add("INVALID_DATE_SEQUENCE", "QuoteAcceptance", a.acceptance_id,
                        f"accepted_at {a.accepted_at} precedes quote creation {q.created_at}", _d(a.accepted_at))
    for p in session.scalars(select(Payment).where(Payment.quote_id.is_not(None))):
        q = quotes.get(p.quote_id)
        if q:
            checked += 1
            if p.created_at < q.created_at:
                failed += 1
                rep.add("INVALID_DATE_SEQUENCE", "Payment", p.payment_id, "payment precedes quote creation", _d(p.created_at))
    for d in session.scalars(select(UnderwritingDecision)):
        q = quotes.get(d.quote_id)
        if q:
            checked += 1
            if d.decided_at < q.created_at:
                failed += 1
                rep.add("INVALID_DATE_SEQUENCE", "UnderwritingDecision", d.decision_id, "decision precedes quote", _d(d.decided_at))
    pols = {p.policy_id: p for p in session.scalars(select(Policy))}
    for p in pols.values():
        q = quotes.get(p.quote_id) if p.quote_id else None
        if q:
            checked += 1
            if p.start_date < q.created_at.date():
                failed += 1
                rep.add("INVALID_DATE_SEQUENCE", "Policy", p.policy_id, "policy starts before its quote was created", p.start_date)
    for e in session.scalars(select(Endorsement)):
        p = pols.get(e.policy_id)
        if p:
            checked += 1
            if not (p.start_date <= e.effective_date <= p.expiry_date):
                failed += 1
                rep.add("INVALID_DATE_SEQUENCE", "Endorsement", e.endorsement_id, "effective date outside policy period", e.effective_date)
    for r in session.scalars(select(Renewal)):
        p = pols.get(r.policy_id)
        if p:
            checked += 1
            if r.new_start_date != p.expiry_date + timedelta(days=1):
                failed += 1
                rep.add("INVALID_DATE_SEQUENCE", "Renewal", r.renewal_id, "new term does not start the day after expiry", r.new_start_date)
    rep.check("date_ordering", checked, failed)


def _lifecycle(session, rep):
    hist = defaultdict(list)
    for h in session.scalars(select(PolicyStatusHistory).order_by(PolicyStatusHistory.history_id)):
        hist[h.policy_id].append(h)
    failed = 0
    pols = session.scalars(select(Policy).order_by(Policy.policy_id)).all()
    for p in pols:
        hs, why = hist.get(p.policy_id, []), None
        if not hs:
            why = "no status history"
        else:
            prev = None
            for h in hs:
                if h.from_status != prev or not can_transition(prev, h.to_status):
                    why = f"invalid transition {h.from_status}->{h.to_status}"
                    break
                prev = h.to_status
            if why is None and prev != p.status:
                why = f"status {p.status} differs from history end {prev}"
        if why:
            failed += 1
            rep.add("LIFECYCLE_VIOLATION", "Policy", p.policy_id, why, p.start_date)
    rep.check("lifecycle_transitions", len(pols), failed)


def _premiums(session, rep):
    checked = failed = 0
    pol_by_quote = {p.quote_id: p for p in session.scalars(select(Policy).where(Policy.quote_id.is_not(None)))}

    def verify(breakdown, recorded, pk):
        return premium_matches(recorded, recalculate_from_snapshot(breakdown, pk)["final_premium"], R.PREMIUM_TOLERANCE)

    for p in session.scalars(select(Policy).order_by(Policy.policy_id)):
        bd = p.snapshot.get("premium_breakdown")
        if bd:
            checked += 1
            if not verify(bd, float(p.premium), p.snapshot["product_key"]):
                failed += 1
                rep.add("PREMIUM_FORMULA_MISMATCH", "Policy", p.policy_id,
                        f"recorded {float(p.premium):.2f} vs recalculated {recalculate_from_snapshot(bd, p.snapshot['product_key'])['final_premium']:.2f}",
                        p.start_date)
    for q in session.scalars(select(Quote).order_by(Quote.quote_id)):
        if not q.premium_breakdown or q.premium is None:          # JSON null != SQL NULL: filter in Python
            continue
        checked += 1
        pk = R.PRODUCT_BY_ID[q.product_id]
        if not verify(q.premium_breakdown, float(q.premium), pk):
            failed += 1
            if q.quote_id in pol_by_quote:                      # attribute to the issued policy (one finding per defect)
                continue
            rep.add("PREMIUM_FORMULA_MISMATCH", "Quote", q.quote_id, "quote premium differs from recalculation", _d(q.created_at))
    for r in session.scalars(select(Renewal).order_by(Renewal.renewal_id)):
        if not r.premium_breakdown or r.offered_premium is None:
            continue
        checked += 1
        pk = R.PRODUCT_BY_ID[session.get(Policy, r.policy_id).product_id] if session.get(Policy, r.policy_id) else None
        if pk and not verify(r.premium_breakdown, float(r.offered_premium), pk):
            failed += 1
            rep.add("PREMIUM_FORMULA_MISMATCH", "Renewal", r.renewal_id, "renewal premium differs from recalculation", r.new_start_date)
    rep.check("premium_reconciliation", checked, failed)


def _limits(session, rep):
    checked = failed = 0
    for e in session.scalars(select(Endorsement).where(Endorsement.status == "APPROVED").order_by(Endorsement.endorsement_id)):
        checked += 1
        s = e.policy_snapshot
        v = check_endorsement_limits(s["product_key"], s["coverage_code"], float(e.coverage_after), float(e.declared_value_after))
        if v:
            failed += 1
            rep.add("ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT", "Endorsement", e.endorsement_id, "; ".join(v), e.effective_date)
    for p in session.scalars(select(Policy)):
        checked += 1
        opt = R.COVERAGE_BY_CODE.get(p.snapshot.get("coverage_code"))
        if opt and not (opt["min_limit"] <= float(p.coverage_amount) <= opt["max_limit"]):
            failed += 1
            rep.add("POLICY_COVERAGE_LIMIT_VIOLATION", "Policy", p.policy_id, "coverage outside option limits", p.start_date)
    rep.check("coverage_limits", checked, failed)


def _issuance(session, rep):
    acc = {a.quote_id for a in session.scalars(select(QuoteAcceptance))}
    paid = {p.quote_id for p in session.scalars(select(Payment).where(Payment.status == "SUCCESS", Payment.quote_id.is_not(None)))}
    cur = {}
    for d in session.scalars(select(UnderwritingDecision).order_by(UnderwritingDecision.quote_id, UnderwritingDecision.sequence)):
        cur[d.quote_id] = d.outcome
    quotes = {q.quote_id: q for q in session.scalars(select(Quote))}
    ren = {r.new_policy_id: r for r in session.scalars(select(Renewal).where(Renewal.new_policy_id.is_not(None)))}
    checked = failed = 0
    for p in session.scalars(select(Policy).order_by(Policy.policy_id)):
        checked += 1
        bad = False
        if p.quote_id:
            q = quotes.get(p.quote_id)
            for cond, issue, msg in ((p.quote_id in acc, "POLICY_WITHOUT_ACCEPTANCE", "no customer acceptance recorded"),
                                     (p.quote_id in paid, "POLICY_WITHOUT_PAYMENT", "no successful payment"),
                                     (cur.get(p.quote_id) == "APPROVED", "POLICY_WITHOUT_APPROVAL", "current decision is not APPROVED"),
                                     (q is not None and q.eligibility_status == "ELIGIBLE", "INELIGIBLE_QUOTE_PROGRESSED", "quote not ELIGIBLE")):
                if not cond:
                    bad = True
                    rep.add(issue, "Policy", p.policy_id, msg, p.start_date)
        elif p.renewal_of_policy_id:
            r = ren.get(p.policy_id)
            if not r or r.status != "ACCEPTED" or r.policy_id != p.renewal_of_policy_id:
                bad = True
                rep.add("POLICY_WITHOUT_ORIGIN", "Policy", p.policy_id, "renewal policy lacks an ACCEPTED renewal record", p.start_date)
        else:
            bad = True
            rep.add("POLICY_WITHOUT_ORIGIN", "Policy", p.policy_id, "policy has neither quote nor renewal origin", p.start_date)
        failed += bad
    rep.check("policy_issuance_conditions", checked, failed)


def _renewals(session, rep):
    checked = failed = 0
    pols = {p.policy_id: p for p in session.scalars(select(Policy))}
    for r in session.scalars(select(Renewal).order_by(Renewal.renewal_id)):
        p = pols.get(r.policy_id)
        if not p:
            continue
        checked += 1
        cancelled = p.status == "CANCELLED" or p.cancelled_at is not None
        generated_after_cancel = p.cancelled_at is not None and r.generated_at.date() > p.cancelled_at
        if cancelled and (r.status in ("GENERATED", "OFFERED", "ACCEPTED") or generated_after_cancel):
            failed += 1
            rep.add("RENEWAL_FOR_CANCELLED_POLICY", "Renewal", r.renewal_id,
                    f"renewal {r.status} exists for cancelled policy {p.policy_id}", r.new_start_date)
        elif r.status == "ACCEPTED" and not r.new_policy_id:
            failed += 1
            rep.add("POLICY_WITHOUT_ORIGIN", "Renewal", r.renewal_id, "ACCEPTED renewal has no new policy", r.new_start_date)
    rep.check("renewal_eligibility", checked, failed)


def _overlaps(session, rep):
    pols = session.scalars(select(Policy).order_by(Policy.policy_id)).all()
    rows = [{"policy_id": p.policy_id, "asset_id": p.asset_id, "product_id": p.product_id, "start_date": p.start_date,
             "expiry_date": p.expiry_date, "status": p.status, "cancelled_on": p.cancelled_at,
             "overlap_reason": p.overlap_reason, "renewal_of_policy_id": p.renewal_of_policy_id} for p in pols]
    pairs = find_unauthorized_overlaps(rows)
    by_id = {p.policy_id: p for p in pols}
    for a, b in pairs:
        later = max(a, b)                                          # the later-issued policy carries the finding
        rep.add("UNAUTHORIZED_POLICY_OVERLAP", "Policy", later, f"overlaps {min(a, b)} on asset {by_id[later].asset_id} without a permitted reason",
                by_id[later].start_date, {"other_policy": min(a, b)})
    rep.check("policy_overlaps", len(pols), len({max(p) for p in pairs}))


def _progression(session, rep):
    checked = failed = 0
    for q in session.scalars(select(Quote).where(Quote.status.in_(("APPROVED", "ACCEPTED", "POLICY_ISSUED")))):
        checked += 1
        if q.eligibility_status != "ELIGIBLE":
            failed += 1
            rep.add("INELIGIBLE_QUOTE_PROGRESSED", "Quote", q.quote_id, f"status {q.status} with eligibility {q.eligibility_status}", _d(q.created_at))
    rep.check("quote_progression", checked, failed)


def to_rows(report: Report, run_id: str, detected_at):
    rows = []
    for i, f in enumerate(report.findings, 1):
        rows.append(DetectedException(exception_id=f"EXC-{run_id}-{i:05d}", run_id=run_id, detected_at=detected_at, **f))
    return rows
