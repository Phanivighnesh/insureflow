"""Pydantic schemas for the AI Copilot API.

All schemas use extra='forbid' (request bodies) or are response-only.
ChatResponse is the single envelope returned by all copilot endpoints.
"""
from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared sub-objects
# ---------------------------------------------------------------------------

class RecordRef(BaseModel):
    """A link to a specific business record that the answer references."""
    type: str                   # quote | policy | applicant | exception | renewal | endorsement
    id: str                     # full formatted ID  e.g. QTE-2026-000001
    label: str                  # human-readable short description
    ui_route: str | None = None  # frontend route hint e.g. /ops/quotes/QTE-2026-000001


class SupportingRule(BaseModel):
    rule_id: str
    text: str


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class ContextRecord(BaseModel):
    type: str   # quote | policy | applicant | exception
    id: str


# ---------------------------------------------------------------------------
# Request bodies  (extra='forbid' — strict)
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    model_config = {"extra": "forbid"}

    question: str = Field(..., min_length=1, max_length=1000)
    context_record: ContextRecord | None = None
    history: list[HistoryMessage] = Field(default_factory=list, max_length=6)


class ExplainDecisionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    quote_id: str


class ExplainExceptionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    exception_id: str


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------

class ChatResponse(BaseModel):
    """Structured copilot response — every field is populated (never None except
    fallback_reason when the LLM succeeded)."""
    answer_id: str                              # AIX-000001
    intent: str                                 # intent catalogue key
    summary: str                                # one-sentence answer
    record_references: list[RecordRef] = []
    key_findings: list[str] = []
    supporting_rules: list[SupportingRule] = []
    explanation: str = ""
    recommended_action: str = ""
    confidence: Literal["high", "medium", "low"] = "low"
    limitations: list[str] = []
    provider: str                               # groq | fallback-templates
    model: str | None = None
    used_fallback: bool
    fallback_reason: str | None = None
    ai_available: bool
    disclaimer: str = (
        "AI explains stored results only. It cannot approve, reject, or change anything."
    )


class AiStatusResponse(BaseModel):
    configured: bool
    provider: str
    model: str | None
    mode: Literal["llm", "fallback-templates"]
    last_call: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Internal: grounded context passed from tools to the prompt/template layer
# ---------------------------------------------------------------------------

class GroundedContext(BaseModel):
    intent: str
    facts: dict[str, Any] = {}
    record_refs: list[RecordRef] = []
    rules: list[SupportingRule] = []
    limitations: list[str] = []
    confidence: Literal["high", "medium", "low"] = "medium"
    not_found: bool = False          # True when the primary record doesn't exist

