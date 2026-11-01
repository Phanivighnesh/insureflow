import base64, json, time
from datetime import date, timedelta

import pytest
from sqlalchemy import select, func

from app.api.deps import create_token
from app.core.config import Settings
from app.models import Applicant, Policy, Quote
from app.services.demo_scenarios import BY_ID
from tests.conftest import login, STAFF_CODE
import copy


def payload(sid, **over):
    p = copy.deepcopy(BY_ID[sid]["payload"]); p.update(over); return p


def submit(api, h, sid, **over):
    r = api.post("/api/customer/quotes", json=payload(sid, **over), headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def issue_policy(api, h, sid="END_TO_END_POLICY"):
    q = submit(api, h, sid)
    assert api.post(f"/api/customer/quotes/{q['quote_id']}/accept", headers=h).status_code == 200
    r = api.post(f"/api/customer/quotes/{q['quote_id']}/payment", json={"outcome": "SUCCESS"}, headers=h)
    assert r.status_code == 200, r.text
    return q["quote_id"], r.json()["policy"]["policy_id"]


# ----------------------------------------------------------------- public + auth
def test_health_and_public_discovery(api):
    assert api.get("/api/health").json()["status"] == "ok"
    pr = api.get("/api/customer/products").json()
    assert [p["product_key"] for p in pr["products"]] == ["MOTOR", "PROPERTY", "COMMERCIAL"]
    assert pr["products"][0]["asset_fields"] and pr["demo_notice"]
    assert len(api.get("/api/customer/demo-scenarios").json()["scenarios"]) == 5


def test_authentication_enforced(api, cust_a):
    assert api.get("/api/quotes").status_code == 401
    assert api.get("/api/quotes", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert api.post("/api/customer/quotes", json=payload("LOW_RISK_AUTO_APPROVE")).status_code == 401
    tok = cust_a["Authorization"].split()[1]
    body, sig = tok.split(".")
    forged = base64.urlsafe_b64encode(json.dumps({"uid": "x", "role": "ADMINISTRATOR", "ck": None, "exp": 9999999999}).encode()).decode().rstrip("=")
    assert api.get("/api/quotes", headers={"Authorization": f"Bearer {forged}.{sig}"}).status_code == 401
    s = Settings(session_secret="test-secret", session_ttl_hours=1)
    expired = create_token(s, "u", "CUSTOMER", "ck_x", now=time.time() - 7200)
    r = api.get("/api/customer/quotes", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED"


def test_staff_session_requires_access_code(api):
    r = api.post("/api/auth/demo-session", json={"role": "ADMINISTRATOR", "access_code": "wrong"})
    assert r.status_code == 403
    assert api.post("/api/auth/demo-session", json={"role": "ADMINISTRATOR"}).status_code == 403
    assert api.get("/api/auth/me", headers=login(api, "ADMINISTRATOR")).json()["role"] == "ADMINISTRATOR"


def test_role_separation(api, cust_a, analyst, reviewer):
    for path in ("/api/quotes", "/api/applicants", "/api/dashboard/summary", "/api/policies", "/api/audit"):
        assert api.get(path, headers=cust_a).status_code == 403, path
    assert api.post("/api/customer/quotes", json=payload("LOW_RISK_AUTO_APPROVE"), headers=analyst).status_code == 403
    assert api.get("/api/customer/quotes", headers=analyst).status_code == 403
    assert api.get("/api/quotes", headers=analyst).status_code == 200 and api.get("/api/quotes", headers=reviewer).status_code == 200


# ------------------------------------------------------- customer -> policy journey
def test_full_customer_to_policy_workflow_visible_to_operations(api, cust_a, analyst):
    q = submit(api, cust_a, "END_TO_END_POLICY")
    qid = q["quote_id"]
    assert q["status"] == "APPROVED" and q["decision"]["rule_ids"] == ["UW-APR-001"] and q["premium"] == 686.75
    assert q["demo_notice"] and q["next_steps"]
    # operations sees the same persisted quote immediately
    ops = api.get(f"/api/quotes/{qid}", headers=analyst).json()
    assert ops["applicant"]["full_name"] == "Lena Hoffmann" and ops["premium_breakdown"]["final_premium"] == 686.75
    assert api.get(f"/api/quotes?q=Hoffmann", headers=analyst).json()["total"] == 1

    # cannot pay before accepting; failed payment issues nothing
    assert api.post(f"/api/customer/quotes/{qid}/payment", json={"outcome": "SUCCESS"}, headers=cust_a).status_code == 409
    assert api.post(f"/api/customer/quotes/{qid}/accept", headers=cust_a).status_code == 200
    assert api.post(f"/api/customer/quotes/{qid}/accept", headers=cust_a).status_code == 409
    r = api.post(f"/api/customer/quotes/{qid}/payment", json={"outcome": "FAILED"}, headers=cust_a).json()
    assert r["policy"] is None and r["demo_payment"] is True
    r = api.post(f"/api/customer/quotes/{qid}/payment", json={"outcome": "SUCCESS", "idempotency_key": "k1"}, headers=cust_a).json()
    pid = r["policy"]["policy_id"]
    assert pid == "POL-2026-000001" and r["policy"]["status"] == "ACTIVE" and r["quote"]["status"] == "POLICY_ISSUED"
    dup = api.post(f"/api/customer/quotes/{qid}/payment", json={"outcome": "SUCCESS", "idempotency_key": "k1"}, headers=cust_a).json()
    assert dup["duplicate_request"] is True and dup["policy"]["policy_id"] == pid

    # customer dashboard
    pol = api.get(f"/api/customer/policies/{pid}", headers=cust_a).json()
    assert pol["premium"] == 686.75 and pol["status_history"][0]["to_status"] == "ACTIVE" and pol["renewal_eligibility"]["eligible"] is False
    assert api.get("/api/customer/policies", headers=cust_a).json()["total"] == 1
    # operations sees policy, audit trail and dashboard counts from the DB
    assert api.get(f"/api/policies/{pid}", headers=analyst).json()["quote_id"] == qid
    ev = [e["event_type"] for e in api.get(f"/api/quotes/{qid}/audit", headers=analyst).json()["events"]]
    for t in ("QUOTE_SUBMITTED", "UNDERWRITING_DECISION", "QUOTE_ACCEPTED", "DEMO_PAYMENT_FAILED", "DEMO_PAYMENT_SUCCESS", "POLICY_ISSUED"):
        assert t in ev, t
    summ = api.get("/api/dashboard/summary", headers=analyst).json()
    assert summ["total_quotes"] == 1 and summ["issued_policies"] == 1 and summ["active_policies"] == 1


# ------------------------------------------------------- cross-customer isolation
def test_cross_customer_access_prevented(api, cust_a, cust_b, analyst):
    qid, pid = issue_policy(api, cust_a)
    q2 = submit(api, cust_a, "MEDIUM_RISK_REFERRAL")["quote_id"]
    for method, path, body in [
        ("get", f"/api/customer/quotes/{qid}", None), ("post", f"/api/customer/quotes/{qid}/accept", None),
        ("post", f"/api/customer/quotes/{qid}/payment", {"outcome": "SUCCESS"}),
        ("post", f"/api/customer/quotes/{q2}/information", {"attributes": {}}),
        ("get", f"/api/customer/policies/{pid}", None), ("post", f"/api/customer/policies/{pid}/cancel", {"reason": "x"}),
        ("post", f"/api/customer/policies/{pid}/renewals", None),
        ("post", f"/api/customer/policies/{pid}/endorsements", {"endorsement_type": "COVERAGE_ADJUSTMENT", "new_coverage_amount": 210000, "effective_date": str(date.today())}),
    ]:
        r = getattr(api, method)(path, headers=cust_b, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (path, r.status_code)
    assert api.get("/api/customer/quotes", headers=cust_b).json()["total"] == 0
    assert api.get("/api/customer/policies", headers=cust_b).json()["total"] == 0
    assert api.get("/api/customer/quotes", headers=cust_a).json()["total"] == 2
    # B's own submission with A's email does not reuse/see A's applicant
    qb = submit(api, cust_b, "END_TO_END_POLICY")
    assert qb["applicant"]["applicant_id"] != api.get(f"/api/customer/quotes/{qid}", headers=cust_a).json()["applicant"]["applicant_id"]
    assert api.get(f"/api/customer/quotes/{qb['quote_id']}", headers=cust_a).status_code == 404
    # policy untouched by B's attempts
    assert api.get(f"/api/policies/{pid}", headers=analyst).json()["status"] == "ACTIVE"


# ------------------------------------------------------------------ underwriting
def test_referral_review_authority_and_stale_decision(api, cust_a, analyst, reviewer):
    q = submit(api, cust_a, "MEDIUM_RISK_REFERRAL")
    qid, did = q["quote_id"], q["decision"]["decision_id"]
    assert q["status"] == "REFERRED" and q["decision"]["approval_authority"] == "OPERATIONS_ANALYST"
    assert api.post(f"/api/customer/quotes/{qid}/accept", headers=cust_a).status_code == 409
    pend = api.get("/api/underwriting/pending", headers=analyst).json()
    assert pend["total"] == 1 and pend["items"][0]["can_act"] is True and pend["items"][0]["referral_reasons"]
    assert api.post(f"/api/underwriting/{did}/approve", json={}, headers=cust_a).status_code == 403
    r = api.post(f"/api/underwriting/{did}/approve", json={"notes": "survey ok"}, headers=analyst)
    assert r.status_code == 200 and r.json()["quote"]["status"] == "APPROVED"
    assert api.post(f"/api/underwriting/{did}/reject", json={}, headers=analyst).status_code == 409    # superseded
    hist = api.get(f"/api/quotes/{qid}", headers=analyst).json()["decision_history"]
    assert [d["outcome"] for d in hist] == ["REFERRED", "APPROVED"] and hist[1]["decided_by"].startswith("operations_analyst")
    assert api.post(f"/api/customer/quotes/{qid}/accept", headers=cust_a).status_code == 200
    assert api.get("/api/underwriting/decisions", params={"quote_id": qid}, headers=analyst).json()["total"] == 2


def test_authority_level_enforced_over_http(api, cust_a, analyst, reviewer):
    p = payload("LOW_RISK_AUTO_APPROVE"); p["asset"]["attributes"]["previous_claims"] = 3
    q = api.post("/api/customer/quotes", json=p, headers=cust_a).json()
    did = q["decision"]["decision_id"]
    assert q["decision"]["approval_authority"] == "RISK_REVIEWER" and q["decision"]["rule_ids"] == ["UW-REF-CLAIMS"]
    assert api.get("/api/underwriting/pending", headers=analyst).json()["items"][0]["can_act"] is False
    assert api.post(f"/api/underwriting/{did}/approve", json={}, headers=analyst).status_code == 403
    assert api.post(f"/api/underwriting/{did}/approve", json={}, headers=reviewer).status_code == 200


def test_declined_premium_hidden_from_customer_but_visible_to_ops(api, cust_a, analyst):
    q = submit(api, cust_a, "HIGH_RISK_DECLINE")
    assert q["status"] == "DECLINED" and q["premium"] is None and q["premium_breakdown"] is None
    ops = api.get(f"/api/quotes/{q['quote_id']}", headers=analyst).json()
    assert ops["premium"] is not None and "UW-DEC-002" in ops["decision"]["rule_ids"]


def test_missing_information_flow(api, cust_a, analyst):
    q = submit(api, cust_a, "MISSING_RISK_INFO")
    assert q["status"] == "PENDING_INFORMATION" and "fire_exposure" in q["eligibility"]["missing_fields"]
    assert q["premium"] is None and "fire_exposure" in q["next_steps"][0]
    assert api.get("/api/underwriting/pending", params={"include_pending_information": True}, headers=analyst).json()["total"] == 1
    r = api.post(f"/api/customer/quotes/{q['quote_id']}/information", json={"attributes": {"fire_exposure": "LOW"}}, headers=cust_a)
    assert r.status_code == 200 and r.json()["eligibility"]["status"] == "ELIGIBLE" and r.json()["premium"] is not None
    assert len(r.json()["decision_history"]) == 2
    # ops can re-run the engine (appends a decision)
    assert len(api.post(f"/api/quotes/{q['quote_id']}/evaluate", headers=analyst).json()["decision_history"]) == 3


def test_validation_and_error_envelope(api, cust_a, analyst):
    r = api.post("/api/customer/quotes", json=payload("LOW_RISK_AUTO_APPROVE", product_key="BOAT"), headers=cust_a)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_FAILED"
    r = api.post("/api/customer/quotes", json={**payload("LOW_RISK_AUTO_APPROVE"), "hack": 1}, headers=cust_a)
    assert r.status_code == 422 and r.json()["error"]["details"]
    r = api.post("/api/customer/quotes", json={"product_key": "MOTOR"}, headers=cust_a)
    assert r.status_code == 422
    assert api.get("/api/quotes/QTE-2026-999999", headers=analyst).status_code == 404
    assert api.get("/api/nope").json()["error"]["code"] == "HTTP_ERROR"


# ------------------------------------------------------- endorsements / renewals
def test_endorsement_flow_and_limit_rejection(api, cust_a, analyst, reviewer):
    _, pid = issue_policy(api, cust_a)
    today = str(date.today())
    ok = api.post(f"/api/customer/policies/{pid}/endorsements", headers=cust_a, json={
        "endorsement_type": "COVERAGE_ADJUSTMENT", "new_coverage_amount": 210000, "effective_date": today}).json()
    assert ok["status"] == "PENDING" and ok["endorsement_id"] == f"END-{pid}-001" and ok["premium_after"] > ok["premium_before"]
    bad = api.post(f"/api/customer/policies/{pid}/endorsements", headers=cust_a, json={
        "endorsement_type": "COVERAGE_ADJUSTMENT", "new_coverage_amount": 2500000, "new_declared_value": 3000000, "effective_date": today}).json()
    assert bad["status"] == "REJECTED" and "ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT" in bad["decision_reason"]
    assert api.post(f"/api/endorsements/{ok['endorsement_id']}/approve", json={}, headers=cust_a).status_code == 403
    assert api.post(f"/api/endorsements/{ok['endorsement_id']}/approve", json={"reason": "ok"}, headers=analyst).json()["status"] == "APPROVED"
    assert api.get("/api/endorsements", params={"policy_id": pid}, headers=analyst).json()["total"] == 2
    assert len(api.get(f"/api/customer/policies/{pid}", headers=cust_a).json()["endorsements"]) == 2
    assert api.post(f"/api/customer/policies/{pid}/endorsements", headers=cust_a, json={
        "endorsement_type": "COVERAGE_ADJUSTMENT", "new_coverage_amount": 210000, "effective_date": "2099-01-01"}).status_code == 422


def test_renewal_and_cancellation_flow(api, cust_a, cust_b, analyst):
    _, pid = issue_policy(api, cust_a)
    assert api.post(f"/api/customer/policies/{pid}/renewals", headers=cust_a).status_code == 409   # outside window today
    expiry = date.fromisoformat(api.get(f"/api/policies/{pid}", headers=analyst).json()["expiry_date"])
    r = api.post("/api/renewals/generate", json={"policy_id": pid, "as_of_date": str(expiry - timedelta(days=20))}, headers=analyst)
    assert r.status_code == 201 and r.json()["status"] == "OFFERED"
    rid = r.json()["renewal_id"]
    assert rid == f"REN-{pid}-{expiry.year + (1 if expiry.month == 12 and expiry.day == 31 else 0) if False else (expiry + timedelta(days=1)).year}"
    assert api.post(f"/api/customer/renewals/{rid}/accept", json={}, headers=cust_b).status_code == 404
    assert api.get("/api/customer/renewals", headers=cust_a).json()["total"] == 1
    acc = api.post(f"/api/customer/renewals/{rid}/accept", json={"payment_outcome": "SUCCESS"}, headers=cust_a).json()
    assert acc["renewal"]["status"] == "ACCEPTED" and acc["new_policy"]["renewal_of_policy_id"] == pid
    assert api.get(f"/api/policies/{pid}", headers=analyst).json()["status"] == "RENEWED"
    assert api.get("/api/renewals", params={"status": "ACCEPTED"}, headers=analyst).json()["total"] == 1
    assert api.get("/api/dashboard/renewals", headers=analyst).json()["outcomes"] == {"ACCEPTED": 1}


def test_cancelled_policy_cannot_be_renewed(api, cust_a, analyst):
    _, pid = issue_policy(api, cust_a)
    assert api.post(f"/api/customer/policies/{pid}/cancel", json={"reason": "sold"}, headers=cust_a).json()["status"] == "CANCELLED"
    r = api.post("/api/renewals/generate", json={"policy_id": pid, "as_of_date": str(date.today() + timedelta(days=330))}, headers=analyst)
    assert r.status_code == 409 and any("RENEWAL_FOR_CANCELLED_POLICY" in d for d in r.json()["error"]["details"])


# ------------------------------------------------------------- lists/dashboards
def test_pagination_filters_and_dashboard_from_db(api, cust_a, analyst):
    for sid in ("LOW_RISK_AUTO_APPROVE", "MEDIUM_RISK_REFERRAL", "HIGH_RISK_DECLINE", "MISSING_RISK_INFO"):
        submit(api, cust_a, sid)
    r = api.get("/api/quotes", params={"page_size": 2, "page": 2}, headers=analyst).json()
    assert r["total"] == 4 and len(r["items"]) == 2 and r["page"] == 2
    assert api.get("/api/quotes", params={"status": "DECLINED"}, headers=analyst).json()["total"] == 1
    assert api.get("/api/quotes", params={"product": "motor"}, headers=analyst).json()["total"] == 2
    ap = api.get("/api/applicants", params={"q": "Asha"}, headers=analyst).json()
    assert ap["total"] == 1 and ap["items"][0]["quote_count"] == 1 and ap["items"][0]["asset_count"] == 1
    det = api.get(f"/api/applicants/{ap['items'][0]['applicant_id']}", headers=analyst).json()
    assert det["assets"] and det["quotes"]
    assert api.get("/api/assets", headers=analyst).json()["total"] == 4
    uw = api.get("/api/dashboard/underwriting", headers=analyst).json()
    assert uw["decision_distribution"] == {"APPROVED": 1, "REFERRED": 1, "DECLINED": 1, "PENDING_INFORMATION": 1}
    assert uw["product_volume"]["MOTOR"] == 2 and sum(b["count"] for b in uw["premium_distribution"]) == 3
    s = api.get("/api/dashboard/summary", headers=analyst).json()
    assert (s["total_quotes"], s["pending_underwriting_reviews"], s["declined_applications"], s["total_applicants"]) == (4, 1, 1, 4)


# ------------------------------------------------------------ schema/migrations
def test_alembic_upgrade_matches_models(tmp_path):
    from alembic import command
    from alembic.config import Config
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine
    from app.database.base import Base
    import app.models  # noqa
    url = f"sqlite:///{tmp_path}/mig.db"
    cfg = Config("alembic.ini"); cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    with eng.connect() as c:
        diff = compare_metadata(MigrationContext.configure(c), Base.metadata)
    assert diff == [], diff
    command.downgrade(cfg, "base")


def test_ddl_compiles_for_postgresql():
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable
    from app.database.base import Base
    import app.models  # noqa
    for t in Base.metadata.sorted_tables:
        assert "CREATE TABLE" in str(CreateTable(t).compile(dialect=postgresql.dialect()))


def test_api_contract_in_sync():
    """docs/API_CONTRACT.md + docs/openapi.json must match the implemented routes."""
    import os
    from scripts.generate_api_contract import DOCS, render
    md, oa = render()
    assert open(os.path.join(DOCS, "API_CONTRACT.md")).read() == md, "run: python -m scripts.generate_api_contract --write"
    assert open(os.path.join(DOCS, "openapi.json")).read() == oa
    ops = sum(1 for v in json.loads(oa)["paths"].values() for m in v if m in ("get", "post", "put", "patch", "delete"))
    assert ops > 50 and f"_{ops} endpoints._" in md          # guards against a vacuous/partial contract


def test_cors_allows_configured_origin_only(api):
    ok = api.options("/api/customer/products", headers={"Origin": "http://localhost:5173",
                                                       "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = api.options("/api/customer/products", headers={"Origin": "http://evil.example",
                                                        "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_transaction_commits_before_response_is_sent(api, cust_a, monkeypatch):
    """Regression (found by live-server frontend tests): data must be durable BEFORE the client receives the response,
    otherwise an immediate follow-up request can read stale data."""
    import asyncio, json
    from sqlalchemy.orm import Session
    events = []
    real_commit = Session.commit
    monkeypatch.setattr(Session, "commit", lambda self: (events.append("commit"), real_commit(self))[1])

    async def call():
        body = json.dumps(payload("LOW_RISK_AUTO_APPROVE")).encode()
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http", "path": "/api/customer/quotes",
                 "raw_path": b"/api/customer/quotes", "query_string": b"", "root_path": "", "server": ("test", 80), "client": ("c", 1),
                 "headers": [(b"content-type", b"application/json"), (b"authorization", cust_a["Authorization"].encode()), (b"content-length", str(len(body)).encode())]}
        sent = {"done": False}

        async def receive():
            if not sent["done"]:
                sent["done"] = True
                return {"type": "http.request", "body": body, "more_body": False}
            await asyncio.sleep(3600)

        async def send(msg):
            events.append(msg["type"])
        await api.app_ref(scope, receive, send)
    asyncio.run(call())
    assert "http.response.start" in events and "commit" in events
    assert events.index("commit") < events.index("http.response.start"), events
