"""Metrics + evaluation against ground truth. This is the ONLY module that reads GroundTruth, and it is
used for evaluation/reporting only - never as an input to engines or the detector."""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy import func, select

from app.engines import validation_engine as V
from app.models import (DetectedException, GroundTruth, Policy, Quote, UnderwritingDecision, ValidationRun)
from app.services import workflow as W

CORE_TABLES = ["applicants", "insured_assets", "quotes", "underwriting_decisions", "payments", "policies",
               "endorsements", "renewals"]


def row_counts(session) -> dict:
    return {t.name: session.scalar(select(func.count()).select_from(t)) for t in V.dataset_tables()}


def _ratio(num, den):
    return round(num / den, 4) if den else None


def business_metrics(session, rep: V.Report) -> dict:
    counts = row_counts(session)
    total_core = sum(counts[t] for t in CORE_TABLES)
    invalid = {(f["affected_entity"], f["affected_record_id"]) for f in rep.findings}
    nq = counts["quotes"]
    cur, first = {}, {}
    for d in session.scalars(select(UnderwritingDecision).order_by(UnderwritingDecision.quote_id, UnderwritingDecision.sequence)):
        cur[d.quote_id] = d.outcome
        first.setdefault(d.quote_id, d.outcome)
    elig = session.scalar(select(func.count()).select_from(Quote).where(Quote.eligibility_status == "ELIGIBLE"))
    prem = [float(p) for (p,) in session.execute(select(Quote.premium).where(Quote.premium.is_not(None)))]
    ck = rep.checks

    def acc(name):
        c = ck.get(name)
        return _ratio(c["checked"] - c["failed"], c["checked"]) if c else None
    return {
        "total_records_processed": total_core, "invalid_records": len(invalid), "valid_records": total_core - len(invalid),
        "exception_counts": dict(Counter(f["issue_type"] for f in rep.findings)), "exception_total": len(rep.findings),
        "eligibility_pass_rate": _ratio(elig, nq),
        "approval_rate": _ratio(sum(1 for v in cur.values() if v == "APPROVED"), nq),
        "rejection_rate": _ratio(sum(1 for v in cur.values() if v == "DECLINED"), nq),
        "referral_rate": _ratio(sum(1 for v in first.values() if v == "REFERRED"), nq),
        "pending_information_rate": _ratio(sum(1 for v in cur.values() if v == "PENDING_INFORMATION"), nq),
        "average_premium": round(sum(prem) / len(prem), 2) if prem else None,
        "premium_reconciliation_accuracy": acc("premium_reconciliation"),
        "policy_issuance_compliance": acc("policy_issuance_conditions"),
        "renewal_eligibility_compliance": acc("renewal_eligibility"),
        "foreign_key_integrity": acc("foreign_key_integrity"), "row_counts": counts,
    }


def evaluate_against_ground_truth(session, findings: list[dict]) -> dict | None:
    gt = session.scalars(select(GroundTruth)).all()
    if not gt:
        return None
    truth = {(g.issue_type, g.affected_record_id) for g in gt if g.record_category == "ANOMALY"}
    found = {(f["issue_type"], f["affected_record_id"]) for f in findings}
    tp, fp, fn = truth & found, found - truth, truth - found
    per = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for k, s in (("tp", tp), ("fp", fp), ("fn", fn)):
        for it, _ in s:
            per[it][k] += 1
    for v in per.values():
        v["precision"], v["recall"] = _ratio(v["tp"], v["tp"] + v["fp"]), _ratio(v["tp"], v["tp"] + v["fn"])
    p, r = _ratio(len(tp), len(tp) + len(fp)), _ratio(len(tp), len(tp) + len(fn))
    return {"ground_truth_anomalies": len(truth), "detected": len(found), "true_positives": len(tp),
            "false_positives": len(fp), "false_negatives": len(fn), "precision": p, "recall": r,
            "f1": round(2 * p * r / (p + r), 4) if p and r else None,
            "per_issue_type": dict(sorted(per.items())),
            "false_positive_examples": sorted(fp)[:10], "false_negative_examples": sorted(fn)[:10],
            "edge_case_labels": dict(Counter(g.issue_type for g in gt if g.record_category == "EDGE_CASE"))}


def run_and_persist_validation(session, triggered_by: str, now: datetime | None = None) -> ValidationRun:
    now = now or W.utcnow()
    started = W.utcnow()
    rep = V.run_validation(session)
    metrics = business_metrics(session, rep)
    evaluation = evaluate_against_ground_truth(session, rep.findings)
    run_id = f"VAL-{session.scalar(select(func.count()).select_from(ValidationRun)) + 1:03d}"
    run = ValidationRun(run_id=run_id, triggered_by=triggered_by, started_at=started, finished_at=W.utcnow(),
                        checks=rep.checks, metrics=metrics, evaluation=evaluation, finding_count=len(rep.findings))
    session.add(run)
    session.flush()
    session.add_all(V.to_rows(rep, run_id, now))
    session.flush()
    return run
