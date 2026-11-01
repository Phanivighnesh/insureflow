"""Integration test for CopilotService orchestrator."""
from app.ai.providers import FakeProvider
from app.ai.ratelimit import RateLimiter
from app.ai.schemas import ChatRequest
from app.ai.service import CopilotService
from app.core.security import Actor


def test_copilot_service_fallback_when_no_provider(session):
    rl = RateLimiter()
    svc = CopilotService(provider=None, rate_limiter=rl)
    actor = Actor(user_id="analyst1", role="OPERATIONS_ANALYST")

    req = ChatRequest(question="What is the auto-approval limit for property?")
    resp = svc.answer(req, actor, read_session=session, write_session=session)

    assert resp.used_fallback is True
    assert resp.provider == "fallback-templates"
    assert resp.fallback_reason == "no_llm_configured"
    assert resp.ai_available is False
    assert "PROPERTY" in str(resp.key_findings)


def test_copilot_service_with_fake_provider(session):
    llm_json = (
        '{"summary": "Summary of rules.", "key_findings": ["Auto-approval limit is $250,000."], '
        '"supporting_rules": [{"rule_id": "RULES_VERSION", "text": "Rules version"}], '
        '"explanation": "Read-only explanation from LLM.", "recommended_action": "Check rules doc.", '
        '"confidence": "high", "limitations": []}'
    )
    fake = FakeProvider(response_json=llm_json)
    rl = RateLimiter()
    svc = CopilotService(provider=fake, rate_limiter=rl)
    actor = Actor(user_id="analyst1", role="OPERATIONS_ANALYST")

    req = ChatRequest(question="What is the auto-approval limit for property?")
    resp = svc.answer(req, actor, read_session=session, write_session=session)

    assert resp.used_fallback is False
    assert resp.provider == "groq"
    assert resp.ai_available is True
    assert resp.summary == "Summary of rules."
    assert len(fake.calls) == 1


def test_copilot_service_guard_triggers_fallback_on_hallucination(session):
    # LLM hallucinates an unknown quote ID
    hallucinating_json = (
        '{"summary": "Quote QTE-2026-999999 was approved.", "key_findings": ["F1"], '
        '"supporting_rules": [], "explanation": "Hallucinated reference to QTE-2026-999999.", '
        '"recommended_action": "None", "confidence": "high", "limitations": []}'
    )
    fake = FakeProvider(response_json=hallucinating_json)
    rl = RateLimiter()
    svc = CopilotService(provider=fake, rate_limiter=rl)
    actor = Actor(user_id="analyst1", role="OPERATIONS_ANALYST")

    req = ChatRequest(question="What is the auto-approval limit for property?")
    resp = svc.answer(req, actor, read_session=session, write_session=session)

    # Must have fallen back to template because of guard rejection
    assert resp.used_fallback is True
    assert resp.provider == "fallback-templates"
    assert "guard_rejected" in (resp.fallback_reason or "")

