import copy

import pytest

from app.services.demo_scenarios import BY_ID
from tests.conftest import login


@pytest.fixture()
def generated(api, admin):
    r = api.post("/api/data/generate", json={"seed": 20261022, "scale": "starter", "anomalies": True,
                                              "confirm": True, "background": False}, headers=admin)
    assert r.status_code == 202, r.text
    return r.json()


def test_generation_requires_admin_and_confirmation(api, admin, analyst, reviewer, cust_a):
    body = {"scale": "starter", "background": False}
    assert api.post("/api/data/generate", json={**body, "confirm": True}, headers=cust_a).status_code == 403
    assert api.post("/api/data/generate", json={**body, "confirm": True}, headers=analyst).status_code == 403
    assert api.post("/api/data/generate", json={**body, "confirm": True}, headers=reviewer).status_code == 403
    assert api.post("/api/data/generate", json={**body, "confirm": True}).status_code == 401
    r = api.post("/api/data/generate", json=body, headers=admin)             # no confirm -> refused
    assert r.status_code == 422 and "confirm" in r.json()["error"]["message"]
    assert api.get("/api/quotes", headers=admin).json()["total"] == 0        # nothing was deleted/created


def test_generate_then_dashboards_show_real_counts(api, admin, analyst, generated):
    st = api.get("/api/data/status", headers=analyst).json()
    assert st["latest_run"]["status"] == "COMPLETED" and st["running"] is False
    assert st["live_row_counts"]["applicants"] == 150 and st["live_row_counts"]["policies"] == 100
    s = api.get("/api/dashboard/summary", headers=analyst).json()
    assert (s["total_applicants"], s["total_quotes"], s["issued_policies"], s["renewals"]) == (150, 200, 100, 60)
    assert s["exception_count"] == 21 and s["pending_underwriting_reviews"] >= 0
    uw = api.get("/api/dashboard/underwriting", headers=analyst).json()
    assert set(uw["decision_distribution"]) <= {"APPROVED", "REFERRED", "DECLINED", "PENDING_INFORMATION"}
    assert sum(uw["policy_lifecycle"].values()) == 100 and uw["average_premium"] > 0
    assert sum(uw["risk_distribution"].values()) == 200
    ex = api.get("/api/dashboard/exceptions", headers=analyst).json()
    assert sum(ex["by_issue_type"].values()) == 21 and len(ex["by_issue_type"]) == 8 and ex["trend"]
    assert sum(api.get("/api/dashboard/renewals", headers=analyst).json()["outcomes"].values()) == 60


def test_validation_run_matches_ground_truth(api, reviewer, analyst, generated):
    assert api.post("/api/validation/run", headers=analyst).status_code == 403
    v = api.post("/api/validation/run", headers=reviewer).json()
    assert v["run_id"] == "VAL-002" and v["finding_count"] == 21
    ev = v["evaluation"]
    assert (ev["precision"], ev["recall"], ev["false_positives"], ev["false_negatives"]) == (1.0, 1.0, 0, 0)
    m = v["metrics"]
    assert m["total_records_processed"] > 0 and 0 < m["approval_rate"] < 1 and m["average_premium"] > 0
    assert api.get("/api/data/validation", headers=analyst).json()["run_id"] == "VAL-002"


def test_exceptions_listing_detail_and_resolution(api, analyst, generated):
    lst = api.get("/api/exceptions", params={"issue_type": "POLICY_WITHOUT_ACCEPTANCE"}, headers=analyst).json()
    assert lst["total"] == 3
    e = lst["items"][0]
    assert e["severity"] == "HIGH" and e["expected_outcome"] and e["actual_outcome"] and e["resolution_status"] == "OPEN"
    assert api.get(f"/api/exceptions/{e['exception_id']}", headers=analyst).json()["affected_entity"] == "Policy"
    bad = api.post(f"/api/exceptions/{e['exception_id']}/resolution", json={"resolution_status": "RESOLVED"}, headers=analyst)
    assert bad.status_code == 422
    ok = api.post(f"/api/exceptions/{e['exception_id']}/resolution",
                  json={"resolution_status": "RESOLVED", "note": "Acceptance re-captured"}, headers=analyst).json()
    assert ok["resolution_status"] == "RESOLVED" and ok["resolved_by"].startswith("operations_analyst")
    assert api.get("/api/exceptions", params={"resolution_status": "RESOLVED"}, headers=analyst).json()["total"] == 1
    assert api.get("/api/policies/" + e["affected_record_id"], headers=analyst).status_code == 200   # link target exists


def test_generated_records_visible_via_operations_api_with_workflow_intact(api, analyst, cust_a, generated):
    q = api.get("/api/quotes", params={"status": "REFERRED", "page_size": 5}, headers=analyst).json()
    assert q["total"] >= 0
    pol = api.get("/api/policies", params={"status": "ACTIVE", "page_size": 1}, headers=analyst).json()["items"][0]
    d = api.get(f"/api/policies/{pol['policy_id']}", headers=analyst).json()
    assert d["status_history"] and d["snapshot"]["premium_breakdown"]["formula_version"]
    # synthetic customers are isolated from any new demo customer
    assert api.get(f"/api/customer/policies/{pol['policy_id']}", headers=cust_a).status_code == 404
    # a new customer submission after generation continues the deterministic ID sequence
    new = api.post("/api/customer/quotes", json=copy.deepcopy(BY_ID["LOW_RISK_AUTO_APPROVE"]["payload"]), headers=cust_a).json()
    assert new["quote_id"] == "QTE-2026-000201" and new["status"] == "APPROVED"


def test_regeneration_replaces_existing_records_and_is_deterministic(api, admin, cust_a, analyst):
    api.post("/api/customer/quotes", json=copy.deepcopy(BY_ID["LOW_RISK_AUTO_APPROVE"]["payload"]), headers=cust_a)
    body = {"seed": 20261022, "scale": "starter", "anomalies": True, "confirm": True, "background": False}
    api.post("/api/data/generate", json=body, headers=admin)
    first = api.get("/api/data/status", headers=analyst).json()["latest_run"]["checksums"]
    assert api.get("/api/customer/quotes", headers=cust_a).json()["total"] == 0        # customer demo data wiped (documented)
    api.post("/api/data/generate", json=body, headers=admin)
    st = api.get("/api/data/status", headers=analyst).json()["latest_run"]
    assert st["run_id"] == "GEN-002" and st["checksums"] == first                      # identical logical output


def test_export_listing_download_and_path_safety(api, reviewer, analyst, generated):
    assert api.get("/api/data/export", headers=analyst).status_code == 403
    ex = api.get("/api/data/export", headers=reviewer).json()
    names = {f["name"] for f in ex["files"]}
    assert {"csv/quotes.csv", "seed_data.sql", "validation_report.json", "ground_truth/ground_truth.csv"} <= names
    assert ex["row_counts"]["quotes"] == 200 and "evaluation only" in ex["notice"]
    r = api.get("/api/data/export/csv/quotes.csv", headers=reviewer)
    assert r.status_code == 200 and r.text.splitlines()[0].startswith("quote_id,")
    assert api.get("/api/data/export/ground_truth/ground_truth.json", headers=reviewer).status_code == 200
    assert api.get("/api/data/export/csv/..%2F..%2Fmanifest.json", headers=reviewer).status_code in (404, 422)
    assert api.get("/api/data/export/csv/nope.csv", headers=reviewer).status_code == 404
    assert api.get("/api/data/export/etc/passwd", headers=reviewer).status_code in (404, 422)
    assert api.get("/api/data/export/csv/quotes.csv", headers=analyst).status_code == 403


def test_reproducibility_endpoint(api, admin, analyst):
    assert api.get("/api/data/reproducibility", headers=analyst).status_code == 404
    r = api.post("/api/data/reproducibility-check", json={"scale": "starter", "background": False}, headers=admin)
    assert r.status_code == 202 and r.json()["identical"] is True
    assert api.get("/api/data/reproducibility", headers=analyst).json()["identical"] is True
