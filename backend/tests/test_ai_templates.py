"""Tests for deterministic templates."""
from app.ai.schemas import GroundedContext, RecordRef, SupportingRule
from app.ai.templates import render


def test_template_render_deterministic():
    ctx = GroundedContext(
        intent="explain_decision",
        facts={
            "quote_id": "QTE-2026-000001",
            "product": "MOTOR",
            "status": "APPROVED",
            "premium": 1118.0,
            "risk_score": 25.0,
            "risk_category": "LOW",
            "current_decision": {
                "outcome": "APPROVED",
                "approval_authority": "AUTOMATED",
                "reasons": [{"rule_id": "UW-APR-001", "message": "Low risk and coverage within auto-approval limit"}],
                "rule_ids": ["UW-APR-001"],
            },
        },
        record_refs=[RecordRef(type="quote", id="QTE-2026-000001", label="Quote QTE-2026-000001")],
        rules=[SupportingRule(rule_id="UW-APR-001", text="Approved")],
        confidence="high",
    )

    r1 = render(ctx, answer_id="AIX-000001")
    r2 = render(ctx, answer_id="AIX-000001")

    assert r1.summary == r2.summary
    assert r1.key_findings == r2.key_findings
    assert r1.explanation == r2.explanation
    assert r1.provider == "fallback-templates"
    assert r1.used_fallback is True
    assert "QTE-2026-000001" in r1.summary
    assert "$1,118.00" in r1.explanation


def test_template_not_found_handling():
    ctx = GroundedContext(
        intent="explain_decision",
        not_found=True,
        limitations=["Quote QTE-2026-999999 was not found in the database."],
        confidence="low",
    )
    res = render(ctx, answer_id="AIX-000002")
    assert "not found" in res.summary.lower()
    assert res.confidence == "low"
    assert res.used_fallback is True


def test_template_unsupported_question():
    ctx = GroundedContext(
        intent="unsupported",
        facts={},
        confidence="low",
        limitations=["Question type not supported."],
    )
    res = render(ctx, answer_id="AIX-000003")
    assert "can't answer" in res.summary.lower()
    assert res.confidence == "low"

