"""Tests for intent detection, ID extraction, and pronoun resolution."""
from app.ai.intents import detect_intent, extract_ids, parse_query


def test_extract_all_id_formats():
    text = (
        "Check QTE-2026-000001 and policy POL-2026-000002 for applicant APP-2026-000003. "
        "Also EXC-VAL-001-00004, REN-POL-2026-000005-2027, END-POL-2026-000006-001, "
        "and decision UWD-2026-000007."
    )
    ids = extract_ids(text)
    assert ids["quote"] == ["QTE-2026-000001"]
    assert ids["policy"] == ["POL-2026-000002"]
    assert ids["applicant"] == ["APP-2026-000003"]
    assert ids["exception"] == ["EXC-VAL-001-00004"]
    assert ids["renewal"] == ["REN-POL-2026-000005-2027"]
    assert ids["endorsement"] == ["END-POL-2026-000006-001"]
    assert ids["decision"] == ["UWD-2026-000007"]


def test_extract_case_insensitivity():
    text = "Look at qte-2026-000042 and pol-2026-000099"
    ids = extract_ids(text)
    assert ids["quote"] == ["QTE-2026-000042"]
    assert ids["policy"] == ["POL-2026-000099"]


def test_extract_malformed_ids_ignored():
    text = "QTE-202-01 QTE-2026-12345 POL-BAD-ID"
    ids = extract_ids(text)
    assert "quote" not in ids
    assert "policy" not in ids


def test_intent_detection_catalogue():
    cases = [
        ("Why was QTE-2026-000001 referred?", "explain_decision"),
        ("What are the reasons this quote was declined? QTE-2026-000002", "explain_decision"),
        ("Explain the risk profile of APP-2026-000001.", "applicant_risk_profile"),
        ("Explain the premium calculation for QTE-2026-000001.", "premium_explanation"),
        ("Explain exception EXC-VAL-001-00001", "anomaly_explanation"),
        ("Summarize the detected policy anomalies.", "anomaly_summary"),
        ("Summarize the history of POL-2026-000001.", "policy_history"),
        ("Why was the renewal declined for this policy?", "renewal_explanation"),
        ("Show audit summary for QTE-2026-000001", "audit_summary"),
        ("Which applications require senior underwriting review?", "senior_review_queue"),
        ("Show the main reasons for high-risk motor applications", "aggregate_insight"),
        ("What is the auto-approval limit for property?", "rules_help"),
        ("What is the weather in London today?", "unsupported"),
    ]
    for question, expected_intent in cases:
        parsed = parse_query(question)
        assert parsed.intent == expected_intent, f"Failed on: {question} (got {parsed.intent})"


def test_pronoun_context_resolution():
    # User asks "Why was it referred?" with context_record set to a quote
    parsed = parse_query(
        "Why was this quote referred?",
        context_record={"type": "quote", "id": "QTE-2026-000045"},
    )
    assert parsed.intent == "explain_decision"
    assert parsed.quote_ids == ["QTE-2026-000045"]

    # User asks about history with policy context
    parsed_pol = parse_query(
        "Summarize its history",
        context_record={"type": "policy", "id": "POL-2026-000012"},
    )
    assert parsed_pol.intent == "policy_history"
    assert parsed_pol.policy_ids == ["POL-2026-000012"]

