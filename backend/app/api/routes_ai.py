"""AI Copilot API router — staff-only, read-only, TransactionalRoute.

Endpoints:
  POST /api/ai/chat                — general question
  POST /api/ai/explain-decision    — forced intent: explain_decision
  POST /api/ai/explain-exception   — forced intent: anomaly_explanation
  GET  /api/ai/status              — provider availability

All endpoints return 403 for customers, 401 for anonymous,
429 for rate limit, 200 (with template fallback) for any LLM failure.
Unknown IDs return a 200 "not found" answer, not a 404.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.ai.providers import make_provider
from app.ai.ratelimit import RateLimiter
from app.ai.schemas import (
    AiStatusResponse, ChatRequest, ChatResponse,
    ExplainDecisionRequest, ExplainExceptionRequest,
)
from app.ai.service import CopilotService
from app.api.deps import TransactionalRoute, get_db, staff_only
from app.core.errors import DomainError
from app.core.security import Actor

router = APIRouter(prefix="/api/ai", tags=["ai"], route_class=TransactionalRoute)


class RateLimitExceededError(DomainError):
    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"


# ---------------------------------------------------------------------------
# Process-scoped singletons (initialised lazily from app state)
# ---------------------------------------------------------------------------

_rate_limiter: RateLimiter | None = None
_service: CopilotService | None = None


def _get_service(request: Request) -> CopilotService:
    global _rate_limiter, _service
    if _service is None:
        settings = request.app.state.settings
        provider = make_provider(settings)
        _rate_limiter = RateLimiter(
            max_requests=settings.ai_rate_limit_per_minute,
            window_seconds=settings.ai_rate_limit_window_seconds,
        )
        _service = CopilotService(provider=provider, rate_limiter=_rate_limiter)
    return _service


def _check_rate_limit(actor: Actor, service: CopilotService) -> None:
    allowed, retry_after = service._rl.check(actor.user_id)
    if not allowed:
        raise RateLimitExceededError(
            f"Rate limit exceeded. Retry after {retry_after} seconds.",
            details=[f"retry_after_seconds:{retry_after}"],
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    request: Request,
    actor: Actor = Depends(staff_only),
    session=Depends(get_db),
):
    svc = _get_service(request)
    _check_rate_limit(actor, svc)
    return svc.answer(body, actor, read_session=session, write_session=session)


@router.post("/explain-decision", response_model=ChatResponse)
def explain_decision(
    body: ExplainDecisionRequest,
    request: Request,
    actor: Actor = Depends(staff_only),
    session=Depends(get_db),
):
    svc = _get_service(request)
    _check_rate_limit(actor, svc)
    return svc.answer_explain_decision(body, actor, read_session=session, write_session=session)


@router.post("/explain-exception", response_model=ChatResponse)
def explain_exception(
    body: ExplainExceptionRequest,
    request: Request,
    actor: Actor = Depends(staff_only),
    session=Depends(get_db),
):
    svc = _get_service(request)
    _check_rate_limit(actor, svc)
    return svc.answer_explain_exception(body, actor, read_session=session, write_session=session)


@router.get("/status", response_model=AiStatusResponse)
def ai_status(
    request: Request,
    actor: Actor = Depends(staff_only),
):
    svc = _get_service(request)
    provider = svc._provider
    settings = request.app.state.settings

    configured = bool(settings.groq_api_key)
    mode = "llm" if (configured and provider and provider.is_available) else "fallback-templates"
    model = provider.model_name if provider else None

    last_call = None
    if provider and hasattr(provider, "state"):
        st = provider.state
        last_call = {
            "last_success_at": st.last_success_at,
            "last_failure_at": st.last_failure_at,
            "last_failure_code": st.last_failure_code,
        }

    return AiStatusResponse(
        configured=configured,
        provider="groq" if configured else "fallback-templates",
        model=model if configured else None,
        mode=mode,
        last_call=last_call,
    )

