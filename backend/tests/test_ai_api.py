"""Tests for the AI Copilot API routes (/api/ai/*).

Verifies:
1. Anonymous requests are rejected with 401.
2. Customer requests are rejected with 403.
3. Operations staff (analyst, reviewer, admin) are permitted with 200.
4. Unknown record IDs return a 200 'not found' answer, never a 404.
5. Strict validation (extra='forbid') returns 422 for extra fields.
6. Rate limiting returns 429.
7. Status endpoint returns provider and mode.
"""
from app.services.demo_scenarios import BY_ID
import copy


def test_ai_anonymous_rejected(api):
    assert api.get("/api/ai/status").status_code == 401
    assert api.post("/api/ai/chat", json={"question": "What is the auto-approval limit?"}).status_code == 401
    assert api.post("/api/ai/explain-decision", json={"quote_id": "QTE-2026-000001"}).status_code == 401
    assert api.post("/api/ai/explain-exception", json={"exception_id": "EXC-VAL-001-00001"}).status_code == 401


def test_ai_customer_forbidden(api, cust_a):
    assert api.get("/api/ai/status", headers=cust_a).status_code == 403
    assert api.post("/api/ai/chat", json={"question": "What is the auto-approval limit?"}, headers=cust_a).status_code == 403
    assert api.post("/api/ai/explain-decision", json={"quote_id": "QTE-2026-000001"}, headers=cust_a).status_code == 403
    assert api.post("/api/ai/explain-exception", json={"exception_id": "EXC-VAL-001-00001"}, headers=cust_a).status_code == 403


def test_ai_staff_permitted(api, analyst, reviewer, admin):
    for staff_headers in (analyst, reviewer, admin):
        r = api.get("/api/ai/status", headers=staff_headers)
        assert r.status_code == 200
        data = r.json()
        assert "mode" in data
        assert "provider" in data


def test_ai_status_endpoint(api, analyst):
    r = api.get("/api/ai/status", headers=analyst)
    assert r.status_code == 200
    data = r.json()
    assert data["provider"] in ("fallback-templates", "groq")
    assert data["mode"] in ("fallback-templates", "llm")
    assert "last_call" in data


def test_ai_explain_decision_unknown_id_returns_200(api, analyst):
    r = api.post("/api/ai/explain-decision", json={"quote_id": "QTE-2026-999999"}, headers=analyst)
    assert r.status_code == 200
    data = r.json()
    assert "not found" in data["summary"].lower()
    assert data["confidence"] == "low"
    assert data["used_fallback"] is True


def test_ai_explain_exception_unknown_id_returns_200(api, analyst):
    r = api.post("/api/ai/explain-exception", json={"exception_id": "EXC-VAL-999-99999"}, headers=analyst)
    assert r.status_code == 200
    data = r.json()
    assert "not found" in data["summary"].lower()
    assert data["confidence"] == "low"
    assert data["used_fallback"] is True


def test_ai_strict_validation(api, analyst):
    # Extra field forbidden
    r = api.post("/api/ai/chat", json={"question": "Hello", "unrecognized_extra_field": 123}, headers=analyst)
    assert r.status_code == 422
    assert "extra" in r.text.lower() or "unrecognized" in r.text.lower() or "validation_failed" in r.text.lower()

    # Question empty/too short
    r2 = api.post("/api/ai/chat", json={"question": ""}, headers=analyst)
    assert r2.status_code == 422

    # Question too long (>1000 chars)
    r3 = api.post("/api/ai/chat", json={"question": "x" * 1001}, headers=analyst)
    assert r3.status_code == 422


def test_ai_chat_flow_against_real_quote(api, cust_a, analyst):
    # Submit a quote as customer
    p = copy.deepcopy(BY_ID["LOW_RISK_AUTO_APPROVE"]["payload"])
    q_resp = api.post("/api/customer/quotes", json=p, headers=cust_a)
    assert q_resp.status_code == 201
    quote_id = q_resp.json()["quote_id"]

    # Ask copilot about this quote
    r = api.post("/api/ai/chat", json={"question": f"Why was {quote_id} approved?"}, headers=analyst)
    assert r.status_code == 200
    data = r.json()
    assert quote_id in data["summary"] or any(r["id"] == quote_id for r in data["record_references"])
    assert data["intent"] == "explain_decision"
    assert "answer_id" in data
    assert data["answer_id"].startswith("AIX-")


def test_ai_rate_limiting(api, analyst):
    from app.api.routes_ai import _get_service
    svc = _get_service(type("FakeReq", (), {"app": type("App", (), {"state": api.app_ref.state})()})())
    old_max = svc._rl._max
    svc._rl._max = 2
    try:
        # Reset window for analyst
        svc._rl.reset("operations_analyst:ann")
        assert api.post("/api/ai/chat", json={"question": "Rule question 1"}, headers=analyst).status_code == 200
        assert api.post("/api/ai/chat", json={"question": "Rule question 2"}, headers=analyst).status_code == 200
        # 3rd request should exceed rate limit
        r3 = api.post("/api/ai/chat", json={"question": "Rule question 3"}, headers=analyst)
        assert r3.status_code == 429
        assert r3.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    finally:
        svc._rl._max = old_max
        svc._rl.reset("operations_analyst:ann")
