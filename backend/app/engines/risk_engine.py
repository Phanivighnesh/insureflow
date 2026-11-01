"""Weighted risk scoring. Missing information is penalised, NEVER scored as zero risk."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict

from app.core import rules_config as R
from app.engines.common import is_missing, band_lookup


@dataclass
class RiskResult:
    score: float
    category: str
    factors: list = field(default_factory=list)
    missing_info: list = field(default_factory=list)
    explanation: str = ""
    rules_version: str = R.RULES_VERSION

    def to_dict(self):
        return asdict(self)


def category_for(score: float) -> str:
    if score <= R.RISK_THRESHOLDS["low_max"]:
        return "LOW"
    if score <= R.RISK_THRESHOLDS["medium_max"]:
        return "MEDIUM"
    return "HIGH"


def _sub_score(scorer, value):
    if "map" in scorer:
        return scorer["map"].get(value)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return band_lookup(scorer["bands"], value)


def assess_risk(product_key: str, ctx: dict) -> RiskResult:
    cfg = R.PRODUCTS[product_key]
    factors, missing = [], []
    total_w = sum(f["weight"] for f in cfg["risk_factors"])
    acc = 0.0
    for f in cfg["risk_factors"]:
        value = ctx.get(f["input"])
        sub = None if is_missing(value) else _sub_score(f["scorer"], value)
        flagged = sub is None
        if flagged:
            sub = R.MISSING_RISK_PENALTY
            reason = "missing" if is_missing(value) else "unrecognised value"
            missing.append({"rsk_id": f["rsk_id"], "input": f["input"], "reason": reason,
                            "mandatory": f["mandatory"]})
        contribution = f["weight"] * sub
        acc += contribution
        factors.append({"rsk_id": f["rsk_id"], "code": f["code"], "label": f["label"],
                        "input": f["input"], "input_value": value, "weight": f["weight"],
                        "sub_score": sub, "contribution": round(contribution / total_w, 4),
                        "penalised_missing": flagged})
    score = round(acc / total_w, 2)
    category = category_for(score)
    top = sorted(factors, key=lambda x: x["contribution"], reverse=True)[:3]
    expl = (f"Weighted risk score {score} ({category}). Top contributors: "
            + "; ".join(f"{t['label']} ({t['contribution']:.1f} pts)" for t in top) + ".")
    if missing:
        expl += (f" {len(missing)} input(s) missing/unrecognised were scored at the "
                 f"{R.MISSING_RISK_PENALTY:.0f}-point penalty, not zero.")
    return RiskResult(score, category, factors, missing, expl)
