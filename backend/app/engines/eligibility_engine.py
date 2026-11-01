"""Eligibility evaluation: ELIGIBLE / INELIGIBLE / NEEDS_INFORMATION (all checks explained)."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict

from app.core import rules_config as R
from app.engines.common import is_missing


@dataclass
class EligibilityResult:
    status: str
    checks: list = field(default_factory=list)
    missing_fields: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def evaluate_eligibility(product_key: str, ctx: dict) -> EligibilityResult:
    cfg = R.PRODUCTS[product_key]
    checks = []

    def add(rule_id, name, passed, msg, severity="BLOCKING"):
        checks.append({"rule_id": rule_id, "name": name, "passed": passed,
                       "severity": severity, "message": msg})

    missing = [f for f in cfg["mandatory"] if is_missing(ctx.get(f))]

    age = ctx.get("applicant_age")
    lo, hi = cfg["applicant_age"]
    if is_missing(age):
        add("ELG-001", "Applicant age", None, "Not evaluated: applicant age missing")
    else:
        add("ELG-001", "Applicant age", lo <= age <= hi, f"Age {age}; allowed {lo}-{hi}")

    dv = ctx.get("declared_value")
    vlo, vhi = cfg["insured_value"]
    if is_missing(dv):
        add("ELG-002", "Declared asset value", None, "Not evaluated: declared value missing")
    else:
        add("ELG-002", "Declared asset value", vlo <= dv <= vhi, f"Value {dv:,.0f}; allowed {vlo:,}-{vhi:,}")

    max_age, a = cfg.get("max_asset_age"), ctx.get("asset_age_years")
    if max_age is not None:
        if is_missing(a):
            add("ELG-003", "Asset age", None, "Not evaluated: asset age unknown")
        else:
            add("ELG-003", "Asset age", 0 <= a <= max_age, f"Asset age {a}y; maximum {max_age}y")

    for fld, allowed in cfg["allowed_values"].items():
        v = ctx.get(fld)
        if is_missing(v):
            add("ELG-004", f"Allowed {fld}", None, f"Not evaluated: {fld} missing")
        else:
            add("ELG-004", f"Allowed {fld}", v in allowed, f"{fld}={v}; allowed {allowed}")

    code, req = ctx.get("coverage_code"), ctx.get("requested_coverage")
    cov = R.COVERAGE_BY_CODE.get(code) if not is_missing(code) else None
    if is_missing(code):
        add("ELG-005", "Coverage option valid for product", None, "Not evaluated: coverage option missing")
    else:
        ok = cov is not None and cov["product_key"] == product_key
        add("ELG-005", "Coverage option valid for product", ok,
            f"{code} is {'valid' if ok else 'not valid'} for {product_key}")
    if cov is not None and cov["product_key"] == product_key and not is_missing(req):
        add("ELG-006", "Requested coverage within option limits",
            cov["min_limit"] <= req <= cov["max_limit"],
            f"Requested {req:,.0f}; option limits {cov['min_limit']:,}-{cov['max_limit']:,}")
    if not is_missing(req) and not is_missing(dv):
        cap = dv * R.MAX_COVERAGE_TO_VALUE_RATIO
        add("ELG-007", "Coverage does not exceed declared value", req <= cap + 1e-9,
            f"Requested {req:,.0f}; cap {cap:,.0f} (declared value x {R.MAX_COVERAGE_TO_VALUE_RATIO})")

    add("ELG-008", "Mandatory information complete", len(missing) == 0,
        "All mandatory fields present" if not missing else f"Missing: {', '.join(missing)}",
        severity="INFO_REQUIRED")

    if any(c["passed"] is False and c["severity"] == "BLOCKING" for c in checks):
        status = "INELIGIBLE"
    elif missing:
        status = "NEEDS_INFORMATION"
    else:
        status = "ELIGIBLE"
    return EligibilityResult(status, checks, missing)
