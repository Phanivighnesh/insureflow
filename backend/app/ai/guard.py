"""Post-generation guard (anti-hallucination verifier).

After the LLM produces an answer, this module verifies deterministically that:
1. Every record ID mentioned exists in GroundedContext.record_refs or facts.
2. Every money amount / score / count in the answer is present in facts (within tolerance).
3. No forbidden claims are made (approving/declining/changing anything).
4. Required fields are present and non-empty.

On failure → returns a GuardResult describing what failed so the caller falls back to templates.
IMPORTANT: GuardResult.detail must NEVER include the LLM's raw content or the API key.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field

from app.ai.schemas import GroundedContext

# ID patterns
_RE_QTE = re.compile(r'\bQTE-\d{4}-\d{6}\b', re.IGNORECASE)
_RE_POL = re.compile(r'\bPOL-\d{4}-\d{6}\b', re.IGNORECASE)
_RE_APP = re.compile(r'\bAPP-\d{4}-\d{6}\b', re.IGNORECASE)
_RE_EXC = re.compile(r'\bEXC-VAL-\d{3}-\d{5}\b', re.IGNORECASE)
_RE_REN = re.compile(r'\bREN-POL-\d{4}-\d{6}-\d{4}\b', re.IGNORECASE)
_RE_END = re.compile(r'\bEND-POL-\d{4}-\d{6}-\d{3}\b', re.IGNORECASE)

# Money / number patterns
_RE_DOLLAR = re.compile(r'\$\s?([\d,]+(?:\.\d{1,2})?)')
_RE_SCORE = re.compile(r'\b(\d{1,3}(?:\.\d{1,2})?)\s*(?:risk\s+score|score\s+of|score:)', re.IGNORECASE)

# Forbidden assertion patterns
_FORBIDDEN = [
    re.compile(r'\b(i\s+have|i\'ve|we\s+have|system\s+has)\s+(approved|declined|rejected|referred|changed|updated|modified|cancelled|created)\b', re.IGNORECASE),
    re.compile(r'\bthis\s+quote\s+(is\s+now|has\s+been)\s+(approved|declined|rejected)\b', re.IGNORECASE),
    re.compile(r'\byour\s+api\s+key\b', re.IGNORECASE),
    re.compile(r'\bGROQ_API_KEY\b'),
    re.compile(r'\bgsk_[A-Za-z0-9]+\b'),  # Groq key pattern
]


@dataclass
class GuardResult:
    passed: bool
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"passed": self.passed, "failures": self.failures}


def _extract_ids_from_text(text: str) -> set[str]:
    ids: set[str] = set()
    for pat in (_RE_QTE, _RE_POL, _RE_APP, _RE_EXC, _RE_REN, _RE_END):
        for m in pat.finditer(text):
            ids.add(m.group(0).upper())
    return ids


def _extract_money_from_text(text: str) -> list[float]:
    amounts = []
    for m in _RE_DOLLAR.finditer(text):
        try:
            amounts.append(float(m.group(1).replace(",", "")))
        except ValueError:
            pass
    return amounts


def _facts_numbers(facts: dict) -> set[float]:
    """Recursively extract all numeric values from facts."""
    nums: set[float] = set()

    def walk(obj):
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            nums.add(round(float(obj), 2))
        elif isinstance(obj, str):
            for m in re.findall(r'-?\d+(?:\.\d+)?', obj):
                try:
                    nums.add(round(float(m), 2))
                except ValueError:
                    pass
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(facts)
    return nums


def _known_ids(ctx: GroundedContext) -> set[str]:
    known: set[str] = set()
    for ref in ctx.record_refs:
        known.add(ref.id.upper())
    # Also extract from facts values
    def walk_ids(obj):
        if isinstance(obj, str):
            for pat in (_RE_QTE, _RE_POL, _RE_APP, _RE_EXC, _RE_REN, _RE_END):
                for m in pat.finditer(obj):
                    known.add(m.group(0).upper())
        elif isinstance(obj, dict):
            for v in obj.values():
                walk_ids(v)
        elif isinstance(obj, list):
            for item in obj:
                walk_ids(item)
    walk_ids(ctx.facts)
    return known


def verify(answer_text: str, parsed_json: dict, ctx: GroundedContext) -> GuardResult:
    """Run all guard checks. Returns GuardResult(passed=True) if all pass."""
    failures = []

    # 1. Required fields present
    for req in ("summary", "key_findings", "explanation"):
        if not parsed_json.get(req):
            failures.append(f"missing_required_field:{req}")

    # 2. ID check — every ID mentioned in the answer must be in known IDs
    known = _known_ids(ctx)
    mentioned = _extract_ids_from_text(answer_text)
    unknown_ids = mentioned - known
    if unknown_ids:
        failures.append(f"unknown_ids:{','.join(sorted(unknown_ids)[:5])}")

    # 3. Money check — every dollar amount mentioned must be in facts (±1.0 tolerance)
    if ctx.facts:
        fact_nums = _facts_numbers(ctx.facts)
        mentioned_amounts = _extract_money_from_text(answer_text)
        for amt in mentioned_amounts:
            # Allow if within 1.0 of any fact number (covers rounding/cents)
            if not any(abs(amt - fn) <= 1.0 for fn in fact_nums):
                failures.append(f"unverifiable_amount:{amt}")

    # 4. Forbidden claims
    for pat in _FORBIDDEN:
        if pat.search(answer_text):
            failures.append(f"forbidden_claim:{pat.pattern[:40]}")
            break  # report first match only (don't leak content)

    # 5. Confidence field validity
    conf = parsed_json.get("confidence", "low")
    if conf not in ("high", "medium", "low"):
        failures.append(f"invalid_confidence:{conf}")

    # 6. Lists bounded
    if len(parsed_json.get("key_findings") or []) > 20:
        failures.append("key_findings_too_long")
    if len(parsed_json.get("supporting_rules") or []) > 15:
        failures.append("supporting_rules_too_long")

    return GuardResult(passed=len(failures) == 0, failures=failures)


def parse_and_verify(raw_content: str, ctx: GroundedContext) -> tuple[dict | None, GuardResult]:
    """Parse the LLM's JSON response and run the guard. Returns (parsed_dict, guard_result)."""
    # Strip markdown fences if the model ignored instructions
    content = raw_content.strip()
    if content.startswith("```"):
        content = re.sub(r'^```[a-z]*\n?', '', content)
        content = re.sub(r'```$', '', content).strip()

    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, ValueError) as exc:
        return None, GuardResult(passed=False, failures=[f"json_parse_error:{type(exc).__name__}"])

    if not isinstance(parsed, dict):
        return None, GuardResult(passed=False, failures=["response_not_object"])

    guard = verify(content, parsed, ctx)
    return parsed, guard

