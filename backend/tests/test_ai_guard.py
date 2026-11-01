"""Tests for anti-hallucination guard."""
from app.ai.guard import verify
from app.ai.schemas import GroundedContext, RecordRef, SupportingRule


def _ctx(quote_id="QTE-2026-000001", premium=1118.0, risk_score=25.0):
    return GroundedContext(
        intent="explain_decision",
        facts={
            "quote_id": quote_id,
            "product": "MOTOR",
            "status": "APPROVED",
            "premium": premium,
            "risk_score": risk_score,
            "current_decision": {
                "outcome": "APPROVED",
                "approval_authority": "AUTOMATED",
                "rule_ids": ["UW-APR-001"],
            },
        },
        record_refs=[RecordRef(type="quote", id=quote_id, label=f"Quote {quote_id}")],
        rules=[SupportingRule(rule_id="UW-APR-001", text="Approved")],
    )


def test_guard_accepts_faithful_answer():
    ctx = _ctx()
    parsed = {
        "summary": "Quote QTE-2026-000001 was approved with $1,118.00 premium.",
        "key_findings": ["Risk score is 25.0.", "Coverage is within limits."],
        "supporting_rules": [{"rule_id": "UW-APR-001", "text": "Approved"}],
        "explanation": "Calculated premium is $1,118.00 under automated approval rules.",
        "recommended_action": "Quote is ready for customer acceptance.",
        "confidence": "high",
        "limitations": [],
    }
    answer_text = str(parsed)
    res = verify(answer_text, parsed, ctx)
    assert res.passed is True
    assert res.failures == []


def test_guard_rejects_unknown_id():
    ctx = _ctx(quote_id="QTE-2026-000001")
    parsed = {
        "summary": "Quote QTE-2026-999999 was approved.",
        "key_findings": ["Approved"],
        "explanation": "Reference to QTE-2026-999999 which does not exist.",
        "confidence": "high",
    }
    answer_text = "Quote QTE-2026-999999 was approved."
    res = verify(answer_text, parsed, ctx)
    assert res.passed is False
    assert any("unknown_ids" in f for f in res.failures)


def test_guard_rejects_invented_money():
    ctx = _ctx(premium=1118.0)
    parsed = {
        "summary": "Quote QTE-2026-000001 was approved with $9,999.00 premium.",
        "key_findings": ["High premium"],
        "explanation": "Total comes to $9,999.00.",
        "confidence": "high",
    }
    answer_text = "Quote QTE-2026-000001 has premium $9,999.00."
    res = verify(answer_text, parsed, ctx)
    assert res.passed is False
    assert any("unverifiable_amount" in f for f in res.failures)


def test_guard_rejects_forbidden_claims():
    ctx = _ctx()
    claims = [
        "I have approved this quote for the applicant.",
        "The system has modified the premium to $1,118.00.",
        "We have declined this quote today.",
    ]
    for claim in claims:
        parsed = {
            "summary": claim,
            "key_findings": ["Updated"],
            "explanation": "Details of change.",
            "confidence": "high",
        }
        res = verify(claim, parsed, ctx)
        assert res.passed is False
        assert any("forbidden_claim" in f for f in res.failures), f"Failed to reject: {claim}"


def test_guard_rejects_missing_required_fields():
    ctx = _ctx()
    parsed = {
        "summary": "",  # missing summary
        "key_findings": [],
        "explanation": "Some explanation",
    }
    res = verify("Text", parsed, ctx)
    assert res.passed is False
    assert any("missing_required_field" in f for f in res.failures)

