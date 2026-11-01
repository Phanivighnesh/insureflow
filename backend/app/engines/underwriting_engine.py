"""Deterministic underwriting decision + approval authority."""
from __future__ import annotations

from app.core import rules_config as R


def level_index(level: str) -> int:
    return R.AUTHORITY_LEVELS.index(level)


def max_level(*levels: str) -> str:
    return max(levels, key=level_index)


def coverage_authority(product_key: str, amount: float) -> str:
    cfg = R.PRODUCTS[product_key]
    if amount <= cfg["auto_approval_limit"]:
        return "AUTOMATED"
    if amount <= cfg["analyst_limit"]:
        return "OPERATIONS_ANALYST"
    if amount <= cfg["reviewer_limit"]:
        return "RISK_REVIEWER"
    return "SENIOR_UNDERWRITER"


def role_can_act(role: str, required_authority: str) -> bool:
    top = R.ROLE_AUTHORITY.get(role)
    if top is None:
        return False
    return level_index(top) >= level_index(required_authority)


def decide(product_key: str, eligibility, risk, ctx: dict) -> dict:
    def out(outcome, authority, reasons):
        return {"outcome": outcome, "approval_authority": authority,
                "reasons": reasons, "rule_ids": [r["rule_id"] for r in reasons],
                "risk_score": risk.score, "engine_version": R.UW_ENGINE_VERSION}

    if eligibility.status == "INELIGIBLE":
        failed = [c["message"] for c in eligibility.checks if c["passed"] is False]
        return out("DECLINED", "AUTOMATED",
                   [{"rule_id": "UW-DEC-001", "message": "Ineligible: " + " | ".join(failed)}])
    if eligibility.status == "NEEDS_INFORMATION":
        return out("PENDING_INFORMATION", "AUTOMATED",
                   [{"rule_id": "UW-PEN-001",
                     "message": "Mandatory information missing: " + ", ".join(eligibility.missing_fields)}])
    if risk.score >= R.DECLINE_RISK_SCORE:
        return out("DECLINED", "AUTOMATED",
                   [{"rule_id": "UW-DEC-002",
                     "message": f"Risk score {risk.score} >= decline threshold {R.DECLINE_RISK_SCORE}"}])

    amount = ctx["requested_coverage"]
    reasons, levels = [], ["AUTOMATED"]
    risk_level = R.RISK_CATEGORY_AUTHORITY[risk.category]
    if risk_level != "AUTOMATED":
        levels.append(risk_level)
        reasons.append({"rule_id": "UW-REF-RISK",
                        "message": f"{risk.category} risk (score {risk.score}) requires {risk_level}"})
    cov_level = coverage_authority(product_key, amount)
    if cov_level != "AUTOMATED":
        levels.append(cov_level)
        reasons.append({"rule_id": "UW-REF-COV",
                        "message": f"Coverage {amount:,.0f} exceeds auto-approval limit "
                                   f"{R.PRODUCTS[product_key]['auto_approval_limit']:,} -> {cov_level}"})
    for rid, rule in R.EXCEPTION_RULES.items():
        v = ctx.get(rule["field"])
        if isinstance(v, (int, float)) and v >= rule["min"]:
            levels.append(rule["authority"])
            reasons.append({"rule_id": rid, "message": rule["message"]})
    required = max_level(*levels)
    if required == "AUTOMATED":
        return out("APPROVED", "AUTOMATED",
                   [{"rule_id": "UW-APR-001",
                     "message": f"Low risk (score {risk.score}) and coverage within auto-approval limit"}])
    return out("REFERRED", required, reasons)
