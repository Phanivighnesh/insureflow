"""Deterministic intent detection and entity extraction for the AI Copilot.

NO LLM is involved here. Intent is resolved by keyword/regex rules with a
documented priority order. Entity IDs are extracted by regex patterns matching
the system's ID formats.

Priority order (highest to lowest):
1. rules_help         — "what is the limit / rule / threshold / auto-approve"
2. explain_decision   — explicit quote ID or "why" + "decision/declined/referred/approved"
3. premium_explanation — "premium" + "explain/break/calcul/how"
4. applicant_risk_profile — explicit APP- ID or "risk profile" + applicant context
5. anomaly_explanation — explicit EXC- ID or "exception" + "explain/what/why"
6. anomaly_summary    — "anomal/exception" + "summar/overview/list/how many"
7. policy_history     — explicit POL- ID or "policy" + "history/summar/what happened"
8. renewal_explanation — "renewal" + "why/declined/withheld/reason"
9. audit_summary      — "audit" + quote/policy ID
10. senior_review_queue — "senior" or "review queue" or "require senior"
11. aggregate_insight — "show/what are/main/top" + "reason/risk/decline/motor/property/commercial"
12. unsupported       — catch-all
"""
from __future__ import annotations
import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# ID patterns (compile once)
# ---------------------------------------------------------------------------

_RE_QUOTE    = re.compile(r'\bQTE-\d{4}-\d{6}\b', re.IGNORECASE)
_RE_POLICY   = re.compile(r'(?<![A-Za-z0-9-])POL-\d{4}-\d{6}(?![A-Za-z0-9-])', re.IGNORECASE)
_RE_APPLICANT = re.compile(r'\bAPP-\d{4}-\d{6}\b', re.IGNORECASE)
_RE_EXCEPTION = re.compile(r'\bEXC-VAL-\d{3}-\d{5}\b', re.IGNORECASE)
_RE_RENEWAL  = re.compile(r'\bREN-POL-\d{4}-\d{6}-\d{4}\b', re.IGNORECASE)
_RE_ENDORSEMENT = re.compile(r'\bEND-POL-\d{4}-\d{6}-\d{3}\b', re.IGNORECASE)
_RE_DECISION = re.compile(r'\bUWD-\d{4}-\d{6}\b', re.IGNORECASE)

_ALL_ID_PATTERNS = [
    ("quote", _RE_QUOTE),
    ("policy", _RE_POLICY),
    ("applicant", _RE_APPLICANT),
    ("exception", _RE_EXCEPTION),
    ("renewal", _RE_RENEWAL),
    ("endorsement", _RE_ENDORSEMENT),
    ("decision", _RE_DECISION),
]


@dataclass
class ParsedQuery:
    intent: str
    quote_ids: list[str]
    policy_ids: list[str]
    applicant_ids: list[str]
    exception_ids: list[str]
    renewal_ids: list[str]
    endorsement_ids: list[str]
    decision_ids: list[str]
    # resolved from context_record when no explicit ID found
    context_type: str | None = None
    context_id: str | None = None


def _upper_ids(matches: list[re.Match]) -> list[str]:
    return [m.group(0).upper() for m in matches]


def extract_ids(text: str) -> dict[str, list[str]]:
    """Return every structured ID found in the text, grouped by type."""
    result: dict[str, list[str]] = {}
    for kind, pattern in _ALL_ID_PATTERNS:
        found = _upper_ids(pattern.finditer(text))
        if found:
            result[kind] = found
    return result


def _has(text: str, *keywords: str) -> bool:
    """Return True if ANY keyword appears (case-insensitive whole-word-ish match)."""
    lo = text.lower()
    return any(kw.lower() in lo for kw in keywords)


def detect_intent(text: str, ids: dict[str, list[str]]) -> str:
    """Resolve intent from text + found IDs. Pure function — no I/O."""
    lo = text.lower()

    # 1. rules_help
    if _has(lo, "what is the limit", "auto-approv", "auto approv", "authority limit",
            "approval limit", "threshold", "what rule", "which rule", "what are the rule",
            "rules help", "how does the rule", "rule for"):
        return "rules_help"

    # 2. audit_summary
    if _has(lo, "audit") and (ids.get("quote") or ids.get("policy") or
                               _has(lo, "trail", "log", "histor", "event", "activity")):
        return "audit_summary"

    # 3. premium_explanation
    if _has(lo, "premium") and _has(lo, "explain", "break", "calcul", "how", "what", "show"):
        return "premium_explanation"

    # 4. explain_decision — explicit quote OR decision keyword + decision-like words
    if ids.get("quote") or ids.get("decision"):
        if _has(lo, "why", "reason", "declin", "refer", "approv", "decision",
                "result", "outcome", "how come", "explain"):
            return "explain_decision"

    # 4. applicant_risk_profile
    if ids.get("applicant") or _has(lo, "risk profile", "applicant risk", "risk of applicant"):
        return "applicant_risk_profile"

    # 5. anomaly_explanation — specific exception
    if ids.get("exception"):
        return "anomaly_explanation"

    # 6. anomaly_summary
    if _has(lo, "anomal", "exception") and _has(lo, "summar", "overview", "list", "how many",
                                                  "show", "all", "count", "total"):
        return "anomaly_summary"

    # 7. policy_history — specific policy ID or history keywords
    if ids.get("policy") or ids.get("renewal") or ids.get("endorsement"):
        if _has(lo, "histor", "summar", "what happened", "timeline", "status", "show",
                "tell me about", "endorsement", "renewal", "payment"):
            return "policy_history"

    # 8. renewal_explanation
    if _has(lo, "renewal") and _has(lo, "why", "reason", "declin", "withheld", "not renew",
                                      "eligible", "eligibil"):
        return "renewal_explanation"

    # 9. audit_summary
    if _has(lo, "audit") and (ids.get("quote") or ids.get("policy") or
                               _has(lo, "trail", "log", "histor", "event", "activity")):
        return "audit_summary"

    # 10. senior_review_queue
    if _has(lo, "senior underwriter", "senior review", "require senior",
            "review queue", "pending referral", "waiting for review",
            "who needs senior", "need senior"):
        return "senior_review_queue"

    # 11. aggregate_insight
    if _has(lo, "show", "what are", "main", "top", "most common", "frequent", "breakdown") and \
       _has(lo, "reason", "risk", "declin", "motor", "property", "commercial", "high risk",
            "medium risk", "refer"):
        return "aggregate_insight"

    # Fallback — try explain_decision if a quote is present
    if ids.get("quote"):
        return "explain_decision"

    # Fallback — try policy_history if a policy is present
    if ids.get("policy"):
        return "policy_history"

    return "unsupported"


def parse_query(question: str, context_record: dict | None = None) -> ParsedQuery:
    """Full parse: extract IDs, resolve context pronouns, detect intent.

    If no relevant ID is found in the text but context_record is provided,
    the context record's ID is used as if it were extracted (for pronoun
    resolution: "this quote", "this policy", etc.).
    """
    ids = extract_ids(question)

    # Resolve context_record for pronoun references
    ctx_type: str | None = None
    ctx_id: str | None = None
    if context_record:
        ct = (context_record.get("type") or "").lower()
        ci = (context_record.get("id") or "").upper()
        if ct and ci:
            ctx_type = ct
            ctx_id = ci
            # Inject context ID into the id dict if text contains pronouns and no explicit ID
            pronoun_signals = ["this", "it", "the quote", "the policy", "the applicant",
                               "the exception", "here", "current"]
            if _has(question, *pronoun_signals) or not any(ids.values()):
                mapping = {
                    "quote": "quote", "policy": "policy",
                    "applicant": "applicant", "exception": "exception",
                    "renewal": "renewal", "endorsement": "endorsement",
                }
                key = mapping.get(ct)
                if key and key not in ids:
                    ids[key] = [ci]

    intent = detect_intent(question, ids)

    return ParsedQuery(
        intent=intent,
        quote_ids=ids.get("quote", []),
        policy_ids=ids.get("policy", []),
        applicant_ids=ids.get("applicant", []),
        exception_ids=ids.get("exception", []),
        renewal_ids=ids.get("renewal", []),
        endorsement_ids=ids.get("endorsement", []),
        decision_ids=ids.get("decision", []),
        context_type=ctx_type,
        context_id=ctx_id,
    )

