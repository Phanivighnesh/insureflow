import csv, inspect, json, os, re
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.data_generator.config import GenConfig, ANOMALY_TYPES_CORE, ANOMALY_TYPES_EXTRA
from app.data_generator.runner import reproducibility_check, run_generation
from app.database.session import make_engine, make_session_factory
from app.engines import validation_engine as V
from app.engines.policy_engine import compute_expiry
from app.models import (Applicant, DatasetRun, Endorsement, GroundTruth, Payment, Policy, Quote, QuoteAcceptance,
                        Renewal, ValidationRun)
from app.services import evaluation

ALL_ANOMALIES = ANOMALY_TYPES_CORE + ANOMALY_TYPES_EXTRA


def build(cfg, out):
    eng = make_engine("sqlite:///:memory:")
    res = run_generation(eng, cfg, out_dir=str(out))
    return eng, make_session_factory(eng), res


@pytest.fixture(scope="module")
def anom(tmp_path_factory):
    out = tmp_path_factory.mktemp("anom")
    eng, Sf, res = build(GenConfig(seed=20261022, scale="starter", anomalies=True), out)
    yield Sf, res, out
    eng.dispose()


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    out = tmp_path_factory.mktemp("clean")
    eng, Sf, res = build(GenConfig(seed=20261022, scale="starter", anomalies=False), out)
    yield Sf, res, out
    eng.dispose()


def test_starter_volumes_exact(anom):
    Sf, res, _ = anom
    c = res["row_counts"]
    assert (c["applicants"], c["quotes"], c["policies"], c["renewals"]) == (150, 200, 100, 60)
    assert res["notes"] == []


def test_ids_follow_conventions(anom):
    Sf, _, _ = anom
    with Sf() as s:
        pats = [(Applicant.applicant_id, r"APP-2026-\d{6}"), (Quote.quote_id, r"QTE-2026-\d{6}"),
                (Policy.policy_id, r"POL-2026-\d{6}"), (Endorsement.endorsement_id, r"END-POL-2026-\d{6}-\d{3}"),
                (Renewal.renewal_id, r"REN-POL-2026-\d{6}-20\d\d")]
        for col, pat in pats:
            assert all(re.fullmatch(pat, v) for (v,) in s.execute(select(col))), pat


def test_clean_baseline_has_zero_findings_and_perfect_reconciliation(clean):
    Sf, res, _ = clean
    with Sf() as s:
        rep = V.run_validation(s)
    assert rep.findings == [], rep.findings[:3]
    assert all(c["failed"] == 0 for c in rep.checks.values())
    m = res["report"]["metrics"]
    assert m["premium_reconciliation_accuracy"] == 1.0 and m["policy_issuance_compliance"] == 1.0
    assert m["foreign_key_integrity"] == 1.0 and m["invalid_records"] == 0
    assert res["report"]["evaluation"]["false_positives"] == 0 and res["report"]["evaluation"]["ground_truth_anomalies"] == 0


def test_all_eight_anomaly_types_injected_and_detected(anom):
    Sf, res, _ = anom
    ev = res["report"]["evaluation"]
    assert set(ev["per_issue_type"]) == set(ALL_ANOMALIES)
    for t in ANOMALY_TYPES_CORE:
        assert ev["per_issue_type"][t]["tp"] == 3, t
    for t in ANOMALY_TYPES_EXTRA:
        assert ev["per_issue_type"][t]["tp"] == 2, t
    assert (ev["false_positives"], ev["false_negatives"]) == (0, 0) and ev["precision"] == 1.0 and ev["recall"] == 1.0


def test_edge_cases_present(anom):
    ev = anom[1]["report"]["evaluation"]["edge_case_labels"]
    for k in ("MISSING_RISK_INFORMATION", "HIGH_RISK_REFERRAL", "MID_TERM_ASSET_CHANGE", "CANCELLED_POLICY", "DECLINED_RENEWAL"):
        assert ev.get(k, 0) > 0, k


def test_anomaly_switch_off_creates_no_anomaly_labels(clean):
    Sf, _, _ = clean
    with Sf() as s:
        assert s.scalar(select(func.count()).select_from(GroundTruth).where(GroundTruth.record_category == "ANOMALY")) == 0
        assert s.scalar(select(func.count()).select_from(GroundTruth)) > 0           # edge cases still labelled


def test_derived_values_are_consistent_with_sources(clean):
    Sf, _, _ = clean
    with Sf() as s:
        for p in s.scalars(select(Policy)):
            assert p.expiry_date == compute_expiry(p.start_date)
            if p.quote_id:
                q = s.get(Quote, p.quote_id)
                assert float(p.premium) == float(q.premium) and float(p.coverage_amount) == float(q.requested_coverage)
                assert p.start_date >= q.created_at.date()
        pays = s.scalars(select(Payment).where(Payment.status == "SUCCESS", Payment.quote_id.is_not(None))).all()
        for pay in pays:
            assert float(pay.amount) == float(s.get(Quote, pay.quote_id).premium)
        assert s.scalar(select(func.count()).select_from(Policy).where(Policy.status == "CANCELLED")) > 0
        for r in s.scalars(select(Renewal).where(Renewal.status == "ACCEPTED")):
            assert s.get(Policy, r.new_policy_id).renewal_of_policy_id == r.policy_id
            assert s.get(Policy, r.policy_id).status == "RENEWED"


def test_cancelled_policies_have_no_live_renewal_in_baseline(clean):
    Sf, _, _ = clean
    with Sf() as s:
        for p in s.scalars(select(Policy).where(Policy.status == "CANCELLED")):
            for r in s.scalars(select(Renewal).where(Renewal.policy_id == p.policy_id)):
                assert r.status == "CANCELLED"


def test_ground_truth_is_separate_and_never_used_by_detector(anom):
    Sf, res, out = anom
    assert os.path.isfile(out / "ground_truth" / "ground_truth.csv") and os.path.isfile(out / "ground_truth" / "ground_truth.json")
    assert not os.path.exists(out / "csv" / "ground_truth.csv")
    import ast
    tree = ast.parse(inspect.getsource(V))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
    assert "GroundTruth" not in names | imported            # the detector never imports or references the label table
    # input tables carry no label columns
    for name in ("quotes", "policies", "payments", "renewals", "endorsements"):
        header = next(csv.reader(open(out / "csv" / f"{name}.csv")))
        assert not {"issue_type", "ground_truth_label", "expected_outcome"} & set(header)
    gt = json.load(open(out / "ground_truth" / "ground_truth.json"))
    assert {g["issue_type"] for g in gt if g["record_category"] == "ANOMALY"} == set(ALL_ANOMALIES)


def test_csv_exports_reference_existing_parents(anom):
    _, _, out = anom
    def ids(name, col):
        return {r[col] for r in csv.DictReader(open(out / "csv" / f"{name}.csv"))}
    q, a, p = ids("quotes", "quote_id"), ids("applicants", "applicant_id"), ids("policies", "policy_id")
    assert {r["applicant_id"] for r in csv.DictReader(open(out / "csv" / "quotes.csv"))} <= a
    assert {r["quote_id"] for r in csv.DictReader(open(out / "csv" / "policies.csv")) if r["quote_id"]} <= q
    assert {r["policy_id"] for r in csv.DictReader(open(out / "csv" / "renewals.csv"))} <= p
    # the labelled INVALID_FOREIGN_KEY rows are the only dangling references in payments
    dangling = [r for r in csv.DictReader(open(out / "csv" / "payments.csv")) if r["policy_id"] and r["policy_id"] not in p]
    assert len(dangling) == 2
    assert os.path.getsize(out / "seed_data.sql") > 0 and os.path.isfile(out / "manifest.json")


def test_run_metadata_persisted_separately(anom):
    Sf, res, out = anom
    with Sf() as s:
        run = s.scalars(select(DatasetRun)).one()
        assert run.status == "COMPLETED" and run.seed == 20261022 and run.row_counts["policies"] == 100
        v = s.scalars(select(ValidationRun)).one()
        assert v.finding_count == 21 and v.evaluation["precision"] == 1.0
    man = json.load(open(out / "manifest.json"))
    assert "generated_at" not in json.dumps(man)                    # timestamps live only in run_metadata.json
    assert "generated_at" in open(out / "run_metadata.json").read()


def test_fixed_seed_reproducibility_and_seed_sensitivity():
    cfg = GenConfig(seed=20261022, scale="starter", anomalies=True)
    rep = reproducibility_check(cfg, runs=2)
    assert rep["identical"] is True and rep["mismatches"] == [] and rep["files_compared"] > 40
    assert any(k.startswith("[ground_truth]") for k in rep["checksums_run1"])
    other = reproducibility_check(GenConfig(seed=7, scale="starter", anomalies=True), runs=1)
    assert other["checksums_run1"]["csv/quotes.csv"] != rep["checksums_run1"]["csv/quotes.csv"]
