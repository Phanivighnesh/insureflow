"""Tests for read-only retrieval tools."""
from app.ai.tools import (
    tool_rules_help,
    tool_explain_decision,
    tool_policy_history,
    tool_applicant_risk_profile,
    tool_premium_explanation,
    tool_anomaly_summary,
    tool_senior_review_queue,
)
from app.core import rules_config as R


def test_tool_rules_help():
    ctx = tool_rules_help("What is the auto-approval limit for property?")
    assert ctx.intent == "rules_help"
    assert ctx.facts["rules_version"] == R.RULES_VERSION
    assert "PROPERTY" in ctx.facts["product_limits"]
    assert ctx.facts["product_limits"]["PROPERTY"]["auto_approval_limit"] == 250000


def test_tool_explain_decision_not_found(session):
    ctx = tool_explain_decision(session, "QTE-2026-999999")
    assert ctx.not_found is True
    assert "not found" in ctx.limitations[0].lower()


def test_tool_policy_history_not_found(session):
    ctx = tool_policy_history(session, "POL-2026-999999")
    assert ctx.not_found is True


def test_tool_applicant_risk_profile_not_found(session):
    ctx = tool_applicant_risk_profile(session, "APP-2026-999999")
    assert ctx.not_found is True


def test_tool_premium_explanation_not_found(session):
    ctx = tool_premium_explanation(session, "QTE-2026-999999")
    assert ctx.not_found is True


def test_tool_senior_review_queue_empty(session):
    ctx = tool_senior_review_queue(session)
    assert ctx.intent == "senior_review_queue"
    assert ctx.facts["total_referred"] == 0
    assert ctx.facts["senior_review_required"] == 0

