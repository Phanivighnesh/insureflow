"""Seed deterministic master data (Product, CoverageOption, ProductCoverage, RiskFactor, ApprovalAuthority)
from the centralised rules config. Idempotent."""
from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Session

from app.core import rules_config as R
from app.models import (ApprovalAuthority, CoverageOption, Product, ProductCoverage, RiskFactor)

EFFECTIVE_FROM = date(2026, 1, 1)


def seed_master_data(session: Session) -> None:
    if session.get(Product, "PROD-001"):
        return
    for key, cfg in R.PRODUCTS.items():
        lo, hi = cfg["insured_value"]
        session.add(Product(product_id=cfg["product_id"], product_key=key, name=cfg["name"],
                            base_rate=cfg["base_rate"], min_insured_value=lo, max_insured_value=hi,
                            effective_from=EFFECTIVE_FROM, rules_version=R.RULES_VERSION))
    session.flush()
    for c in R.COVERAGE_OPTIONS:
        session.add(CoverageOption(coverage_id=c["coverage_id"], code=c["code"], name=c["name"],
                                   min_limit=c["min_limit"], max_limit=c["max_limit"],
                                   rate_multiplier=c["rate_multiplier"]))
    session.flush()
    for c in R.COVERAGE_OPTIONS:
        session.add(ProductCoverage(product_id=R.PRODUCTS[c["product_key"]]["product_id"],
                                    coverage_id=c["coverage_id"], effective_from=EFFECTIVE_FROM))
    for key, cfg in R.PRODUCTS.items():
        for f in cfg["risk_factors"]:
            session.add(RiskFactor(risk_factor_id=f["rsk_id"], product_id=cfg["product_id"], code=f["code"],
                                   label=f["label"], input_field=f["input"], weight=f["weight"],
                                   mandatory=f["mandatory"]))
        limits = {"AUTOMATED": (cfg["auto_approval_limit"], "LOW"),
                  "OPERATIONS_ANALYST": (cfg["analyst_limit"], "MEDIUM"),
                  "RISK_REVIEWER": (cfg["reviewer_limit"], "MEDIUM"),
                  "SENIOR_UNDERWRITER": (None, "HIGH")}
        role_for = {v: k for k, v in R.ROLE_AUTHORITY.items() if v}
        for level, (mx, cat) in limits.items():
            session.add(ApprovalAuthority(authority_id=f"AUTH-{key}-{level}", product_id=cfg["product_id"],
                                          level=level, role=role_for.get(level), max_coverage=mx,
                                          max_risk_category=cat))
    session.flush()
