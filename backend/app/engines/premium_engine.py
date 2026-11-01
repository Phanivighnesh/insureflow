"""Transparent, reproducible premium engine (Decimal arithmetic, HALF_UP rounding).

Base       = coverage_amount x product.base_rate x coverage.rate_multiplier
Adjusted   = round2( Base x age_factor x location_factor x claims_factor x risk_factor )
Final      = Adjusted + sum(fixed charges)
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP

from app.core import rules_config as R
from app.engines.common import band_lookup


def _d(x) -> Decimal:
    return Decimal(str(x))


def _q2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_premium(product_key: str, *, coverage_amount, coverage_code, asset_age_years,
                      location_tier, prior_claims, risk_category) -> dict:
    cfg = R.PRODUCTS[product_key]
    cov = R.COVERAGE_BY_CODE[coverage_code]
    if cov["product_key"] != product_key:
        raise ValueError(f"{coverage_code} is not a {product_key} coverage option")

    base = _d(coverage_amount) * _d(cfg["base_rate"]) * _d(cov["rate_multiplier"])

    if cfg["age_factor"] is None:
        age_f = Decimal("1")
    else:
        if asset_age_years is None:
            raise ValueError("asset_age_years required")
        age_f = _d(band_lookup(cfg["age_factor"], asset_age_years))
    loc_f = _d(cfg["location_factor"][location_tier])
    if prior_claims is None:
        claims_f = _d(R.UNKNOWN_CLAIMS_FACTOR)
    else:
        claims_f = _d(band_lookup(R.CLAIMS_FACTOR, prior_claims))
    risk_f = _d(R.RISK_CATEGORY_FACTOR[risk_category])

    adjusted = _q2(base * age_f * loc_f * claims_f * risk_f)
    charges = {k: float(_q2(_d(v))) for k, v in cfg["fixed_charges"].items()}
    final = adjusted + sum(_d(v) for v in charges.values())
    return {
        "formula_version": R.PREMIUM_FORMULA_VERSION,
        "rules_version": R.RULES_VERSION,
        "currency": R.CURRENCY,
        "inputs": {"coverage_amount": float(coverage_amount), "coverage_code": coverage_code,
                   "asset_age_years": asset_age_years, "location_tier": location_tier,
                   "prior_claims": prior_claims, "risk_category": risk_category},
        "base_rate": cfg["base_rate"],
        "coverage_rate_multiplier": cov["rate_multiplier"],
        "base_premium": float(_q2(base)),
        "factors": {"age": float(age_f), "location": float(loc_f),
                    "claims": float(claims_f), "risk": float(risk_f)},
        "adjusted_premium": float(adjusted),
        "charges": charges,
        "final_premium": float(_q2(final)),
        "formula": "round2(coverage x base_rate x cov_mult x age x location x claims x risk) + fixed charges",
    }


def recalculate_from_snapshot(snapshot: dict, product_key: str) -> dict:
    """Independent recalculation purely from the stored input snapshot."""
    return calculate_premium(product_key, **snapshot["inputs"])


def premium_matches(recorded, recalculated, tolerance: float = R.PREMIUM_TOLERANCE) -> bool:
    return abs(_d(recorded) - _d(recalculated)) <= _d(tolerance)
