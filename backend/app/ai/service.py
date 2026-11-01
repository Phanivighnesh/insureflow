"""Orchestrator service: question → intent → tools → (LLM|template) → guard → response.

The session passed in MUST be read-only (enforced by the router using a
read-only session factory). The service itself never calls session.add/delete/commit.

Governance:
- Never imports or queries GroundTruth
- Never imports from services.workflow (only tools.py does DB reads)
- LLM result is always verified by guard.py; fallback on any failure
- AiInteraction is written at the end (by the router, after the response is built,
  using a separate writable session passed in as `write_session`)
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.ai.guard import parse_and_verify
from app.ai.intents import parse_query
from app.ai.prompts import PROMPT_VERSION, build_messages
from app.ai.providers import LLMProvider, ProviderError, ProviderResult
from app.ai.ratelimit import RateLimiter
from app.ai.schemas import (
    ChatResponse, ChatRequest, ContextRecord, ExplainDecisionRequest,
    ExplainExceptionRequest, GroundedContext,
)
from app.ai.templates import render
from app.ai.tools import call_tools, tool_explain_decision, tool_anomaly_explanation
from app.core.security import Actor


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def _next_answer_id(write_session: Session) -> str:
    """Generate the next AIX-NNNNNN answer ID using the shared IdCounter."""
    from app.services.ids import next_seq
    seq = next_seq(write_session, "AIX")
    return f"AIX-{seq:06d}"


# ---------------------------------------------------------------------------
# Main answer orchestrator
# ---------------------------------------------------------------------------

class CopilotService:
    def __init__(self, provider: LLMProvider | None, rate_limiter: RateLimiter):
        self._provider = provider
        self._rl = rate_limiter

    def answer(
        self,
        request: ChatRequest,
        actor: Actor,
        read_session: Session,
        write_session: Session,
    ) -> ChatResponse:
        """Full orchestration: parse → tools → (LLM|template) → guard → persist → return."""
        start_ms = time.monotonic()

        # 1. Parse intent + entities
        ctx_dict = request.context_record.model_dump() if request.context_record else None
        parsed = parse_query(request.question, ctx_dict)

        # 2. Call read-only tools
        ctx: GroundedContext = call_tools(read_session, parsed)

        # 3. Generate answer ID
        answer_id = _next_answer_id(write_session)

        # 4. If intent is unsupported → template immediately (no LLM call)
        if ctx.intent == "unsupported":
            resp = render(ctx, answer_id, ai_available=self._provider_available(),
                          fallback_reason="unsupported_intent")
            self._persist(write_session, actor, request.question, ctx, resp,
                          latency_ms=int((time.monotonic() - start_ms) * 1000))
            return resp

        # 5. Try LLM if available
        provider_used = "fallback-templates"
        model_used = None
        used_fallback = True
        fallback_reason: str | None = None
        ai_available = self._provider_available()

        if ai_available and self._provider is not None:
            history = [m.model_dump() for m in (request.history or [])]
            messages = build_messages(ctx, request.question, history)
            result = self._provider.generate(messages)

            if isinstance(result, ProviderResult):
                parsed_json, guard = parse_and_verify(result.content, ctx)
                if guard.passed and parsed_json is not None:
                    # LLM answer accepted
                    resp = self._build_from_llm(parsed_json, ctx, answer_id,
                                                result.model_used or self._provider.model_name,
                                                guard)
                    provider_used = "groq"
                    model_used = result.model_used
                    used_fallback = False
                    self._persist(write_session, actor, request.question, ctx, resp,
                                  latency_ms=int((time.monotonic() - start_ms) * 1000),
                                  guard_result=guard.to_dict())
                    return resp
                else:
                    fallback_reason = "guard_rejected:" + ",".join(guard.failures[:3])
            elif isinstance(result, ProviderError):
                fallback_reason = f"provider_error:{result.code}"
                if result.code in ("auth", "model_not_found"):
                    ai_available = False

        # 6. Fallback to deterministic template
        if not fallback_reason:
            fallback_reason = "no_llm_configured"

        resp = render(ctx, answer_id, ai_available=ai_available,
                      fallback_reason=fallback_reason)
        self._persist(write_session, actor, request.question, ctx, resp,
                      latency_ms=int((time.monotonic() - start_ms) * 1000))
        return resp

    def answer_explain_decision(
        self, request: ExplainDecisionRequest, actor: Actor,
        read_session: Session, write_session: Session,
    ) -> ChatResponse:
        ctx = tool_explain_decision(read_session, request.quote_id)
        answer_id = _next_answer_id(write_session)
        synthetic_request = ChatRequest(
            question=f"Explain the underwriting decision for {request.quote_id}.",
        )
        return self._answer_with_context(ctx, synthetic_request, actor,
                                         read_session, write_session, answer_id)

    def answer_explain_exception(
        self, request: ExplainExceptionRequest, actor: Actor,
        read_session: Session, write_session: Session,
    ) -> ChatResponse:
        ctx = tool_anomaly_explanation(read_session, request.exception_id)
        answer_id = _next_answer_id(write_session)
        synthetic_request = ChatRequest(
            question=f"Explain exception {request.exception_id}.",
        )
        return self._answer_with_context(ctx, synthetic_request, actor,
                                         read_session, write_session, answer_id)

    # ------------------------------------------------------------------
    def _answer_with_context(
        self, ctx: GroundedContext, request: ChatRequest, actor: Actor,
        read_session: Session, write_session: Session, answer_id: str,
    ) -> ChatResponse:
        start_ms = time.monotonic()
        ai_available = self._provider_available()
        fallback_reason: str | None = None

        if ai_available and self._provider is not None:
            messages = build_messages(ctx, request.question, [])
            result = self._provider.generate(messages)
            if isinstance(result, ProviderResult):
                parsed_json, guard = parse_and_verify(result.content, ctx)
                if guard.passed and parsed_json is not None:
                    resp = self._build_from_llm(parsed_json, ctx, answer_id,
                                                result.model_used, guard)
                    self._persist(write_session, actor, request.question, ctx, resp,
                                  latency_ms=int((time.monotonic() - start_ms) * 1000),
                                  guard_result=guard.to_dict())
                    return resp
                else:
                    fallback_reason = "guard_rejected:" + ",".join(guard.failures[:3])
            elif isinstance(result, ProviderError):
                fallback_reason = f"provider_error:{result.code}"

        if not fallback_reason:
            fallback_reason = "no_llm_configured"

        resp = render(ctx, answer_id, ai_available=ai_available, fallback_reason=fallback_reason)
        self._persist(write_session, actor, request.question, ctx, resp,
                      latency_ms=int((time.monotonic() - start_ms) * 1000))
        return resp

    def _provider_available(self) -> bool:
        return self._provider is not None and self._provider.is_available

    @staticmethod
    def _build_from_llm(parsed: dict, ctx: GroundedContext, answer_id: str,
                         model_used: str | None, guard) -> ChatResponse:
        from app.ai.schemas import SupportingRule
        rules = [
            SupportingRule(rule_id=r.get("rule_id", ""), text=r.get("text", ""))
            for r in (parsed.get("supporting_rules") or [])
            if isinstance(r, dict) and r.get("rule_id")
        ]
        # Merge LLM rules with context rules (deduplicate by rule_id)
        seen = {r.rule_id for r in rules}
        for r in ctx.rules:
            if r.rule_id not in seen:
                rules.append(r)
                seen.add(r.rule_id)

        conf = parsed.get("confidence", "low")
        if conf not in ("high", "medium", "low"):
            conf = ctx.confidence

        return ChatResponse(
            answer_id=answer_id,
            intent=ctx.intent,
            summary=str(parsed.get("summary", ""))[:500],
            record_references=ctx.record_refs,
            key_findings=[str(f)[:300] for f in (parsed.get("key_findings") or [])[:15]],
            supporting_rules=rules[:10],
            explanation=str(parsed.get("explanation", ""))[:2000],
            recommended_action=str(parsed.get("recommended_action", ""))[:500],
            confidence=conf,
            limitations=([str(l) for l in parsed.get("limitations") or []] + ctx.limitations)[:5],
            provider="groq",
            model=model_used,
            used_fallback=False,
            fallback_reason=None,
            ai_available=True,
            disclaimer="AI explains stored results only. It cannot approve, reject, or change anything.",
        )

    @staticmethod
    def _persist(write_session: Session, actor: Actor, question: str,
                 ctx: GroundedContext, resp: ChatResponse, latency_ms: int,
                 guard_result: dict | None = None) -> None:
        """Write AiInteraction row. Never raises — errors are logged silently."""
        try:
            from app.models import AiInteraction  # imported here to avoid circular
            row = AiInteraction(
                interaction_id=resp.answer_id,
                user_id=actor.user_id,
                role=actor.role,
                question=question[:500],
                intent=ctx.intent,
                record_refs=[r.model_dump() for r in ctx.record_refs[:10]],
                provider=resp.provider,
                model=resp.model,
                used_fallback=resp.used_fallback,
                fallback_reason=resp.fallback_reason,
                guard_result=guard_result,
                latency_ms=latency_ms,
                prompt_version=PROMPT_VERSION,
                created_at=_utcnow(),
            )
            write_session.add(row)
            # Note: commit happens in TransactionalRoute, not here.
        except Exception:
            pass  # persistence failures must not affect the response
