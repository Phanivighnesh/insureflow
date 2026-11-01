import pytest
from datetime import date

from app.core import rules_config as R
from app.engines.eligibility_engine import evaluate_eligibility
from app.engines.policy_engine import (can_transition, check_endorsement_limits, check_issuance_prerequisites,
                                       check_renewal_eligibility, compute_expiry, find_unauthorized_overlaps)
from app.engines.premium_engine import calculate_premium, premium_matches, recalculate_from_snapshot
from app.engines.risk_engine import assess_risk, category_for
from app.engines.underwriting_engine import decide, role_can_act, coverage_authority
from app.services.workflow import build_context


def motor_ctx(**kw):
    base = dict(vehicle_type="SEDAN", manufacturing_year=2024, registration_location="Alderbrook",
                previous_accidents=0, previous_claims=0)
    base.update(kw)
    return build_context("MOTOR", 34, "Alderbrook", 32000, base, "MOTOR_COMPREHENSIVE", 30000)


# ------------------------------------------------------------------ premium
def test_premium_formula_exact():
    # 30000 x 0.04 x 1.0 = 1200 ; x0.95(age 2) x0.95(LOW loc) x1.0 x1.0 = 1083.00 ; +25 +10 = 1118.00
    p = calculate_premium("MOTOR", coverage_amount=30000, coverage_code="MOTOR_COMPREHENSIVE", asset_age_years=2,
                          location_tier="LOW", prior_claims=0, risk_category="LOW")
    assert p["base_premium"] == 1200.0 and p["adjusted_premium"] == 1083.0 and p["final_premium"] == 1118.0
    assert p["factors"] == {"age": 0.95, "location": 0.95, "claims": 1.0, "risk": 1.0}


def test_premium_recalculation_matches_and_detects_mismatch():
    p = calculate_premium("PROPERTY", coverage_amount=200000, coverage_code="PROP_BUILDING_PLUS", asset_age_years=5,
                          location_tier="LOW", prior_claims=0, risk_category="LOW")
    again = recalculate_from_snapshot(p, "PROPERTY")
    assert premium_matches(p["final_premium"], again["final_premium"])
    assert not premium_matches(p["final_premium"] + 5, again["final_premium"])
    assert premium_matches(p["final_premium"] + 0.01, again["final_premium"])      # tolerance boundary


def test_unknown_claims_uses_conservative_factor():
    p = calculate_premium("COMMERCIAL", coverage_amount=100000, coverage_code="COMM_PROPERTY_ONLY", asset_age_years=None,
                          location_tier="MEDIUM", prior_claims=None, risk_category="MEDIUM")
    assert p["factors"]["claims"] == R.UNKNOWN_CLAIMS_FACTOR and p["factors"]["age"] == 1.0


# ---------------------------------------------------------------- eligibility
def test_eligible_motor():
    assert evaluate_eligibility("MOTOR", motor_ctx()).status == "ELIGIBLE"


def test_ineligible_vehicle_type_and_age():
    r = evaluate_eligibility("MOTOR", motor_ctx(vehicle_type="RACING"))
    assert r.status == "INELIGIBLE"
    r = evaluate_eligibility("MOTOR", motor_ctx(manufacturing_year=2000))   # 26y > 20y
    assert r.status == "INELIGIBLE"


def test_missing_mandatory_needs_information_but_ineligible_takes_precedence():
    assert evaluate_eligibility("MOTOR", motor_ctx(previous_accidents=None)).status == "NEEDS_INFORMATION"
    assert evaluate_eligibility("MOTOR", motor_ctx(previous_accidents=None, vehicle_type="RACING")).status == "INELIGIBLE"


def test_coverage_limits_and_value_cap():
    ctx = motor_ctx()
    ctx["requested_coverage"] = 40000                                  # > declared 32000
    assert evaluate_eligibility("MOTOR", ctx).status == "INELIGIBLE"
    ctx["requested_coverage"] = 1000                                   # < option min 2000
    assert evaluate_eligibility("MOTOR", ctx).status == "INELIGIBLE"


def test_applicant_age_boundary():
    for age, expected in [(17, "INELIGIBLE"), (18, "ELIGIBLE"), (80, "ELIGIBLE"), (81, "INELIGIBLE")]:
        ctx = motor_ctx(); ctx["applicant_age"] = age
        assert evaluate_eligibility("MOTOR", ctx).status == expected


# ----------------------------------------------------------------------- risk
def test_risk_low_and_known_score():
    r = assess_risk("MOTOR", motor_ctx())
    assert r.score == 9.75 and r.category == "LOW" and not r.missing_info


def test_risk_missing_is_penalised_not_zero():
    full = assess_risk("MOTOR", motor_ctx(previous_claims=0))
    miss = assess_risk("MOTOR", motor_ctx(previous_claims=None))
    assert miss.score > full.score and any(m["input"] == "previous_claims" for m in miss.missing_info)


def test_risk_thresholds_boundaries():
    assert [category_for(s) for s in (0, 30, 30.01, 70, 70.01, 100)] == ["LOW", "LOW", "MEDIUM", "MEDIUM", "HIGH", "HIGH"]


# --------------------------------------------------------------- underwriting
def _decide(ctx, pk="MOTOR"):
    return decide(pk, evaluate_eligibility(pk, ctx), assess_risk(pk, ctx), ctx)


def test_low_risk_auto_approved():
    d = _decide(motor_ctx())
    assert d["outcome"] == "APPROVED" and d["approval_authority"] == "AUTOMATED"


def test_low_risk_over_auto_limit_is_referred():
    ctx = build_context("MOTOR", 34, "Alderbrook", 60000, motor_attrs(), "MOTOR_COMPREHENSIVE", 50000)
    d = _decide(ctx)
    assert d["outcome"] == "REFERRED" and d["approval_authority"] == "OPERATIONS_ANALYST" and "UW-REF-COV" in d["rule_ids"]


def motor_attrs(**kw):
    a = dict(vehicle_type="SEDAN", manufacturing_year=2024, registration_location="Alderbrook",
             previous_accidents=0, previous_claims=0)
    a.update(kw)
    return a


def test_medium_risk_referred_to_analyst():
    ctx = build_context("MOTOR", 34, "Riverton", 32000, motor_attrs(vehicle_type="SUV", manufacturing_year=2016,
                        previous_accidents=1, previous_claims=1), "MOTOR_COMPREHENSIVE", 30000)
    d = _decide(ctx)
    assert d["outcome"] == "REFERRED" and d["approval_authority"] == "OPERATIONS_ANALYST"


def test_high_risk_never_auto_approved_and_extreme_declined():
    ctx = build_context("MOTOR", 30, "Stormvale", 22000, motor_attrs(vehicle_type="SPORTS", manufacturing_year=2008,
                        previous_accidents=4, previous_claims=4), "MOTOR_COMPREHENSIVE", 20000)
    d = _decide(ctx)
    assert d["outcome"] == "DECLINED" and "UW-DEC-002" in d["rule_ids"]
    ctx = build_context("MOTOR", 30, "Stormvale", 22000, motor_attrs(vehicle_type="SPORTS", manufacturing_year=2010,
                        previous_accidents=2, previous_claims=0), "MOTOR_COMPREHENSIVE", 20000)
    d = _decide(ctx)
    assert d["outcome"] in ("REFERRED", "DECLINED") and d["outcome"] != "APPROVED"


def test_exception_rule_claims_escalates_to_reviewer():
    ctx = build_context("MOTOR", 34, "Alderbrook", 32000, motor_attrs(previous_claims=3), "MOTOR_COMPREHENSIVE", 30000)
    d = _decide(ctx)
    assert d["outcome"] == "REFERRED" and d["approval_authority"] == "RISK_REVIEWER" and "UW-REF-CLAIMS" in d["rule_ids"]


def test_missing_info_pending():
    assert _decide(motor_ctx(previous_accidents=None))["outcome"] == "PENDING_INFORMATION"


def test_role_authority_matrix():
    assert not role_can_act("CUSTOMER", "AUTOMATED")
    assert role_can_act("OPERATIONS_ANALYST", "OPERATIONS_ANALYST") and not role_can_act("OPERATIONS_ANALYST", "RISK_REVIEWER")
    assert role_can_act("RISK_REVIEWER", "RISK_REVIEWER") and not role_can_act("RISK_REVIEWER", "SENIOR_UNDERWRITER")
    assert role_can_act("ADMINISTRATOR", "SENIOR_UNDERWRITER")
    assert coverage_authority("MOTOR", 40000) == "AUTOMATED" and coverage_authority("MOTOR", 40001) == "OPERATIONS_ANALYST"
    assert coverage_authority("MOTOR", 120001) == "SENIOR_UNDERWRITER"


# --------------------------------------------------------------------- policy
def test_lifecycle_transitions():
    assert can_transition("ACTIVE", "CANCELLED") and can_transition("ACTIVE", "RENEWED")
    assert not can_transition("CANCELLED", "ACTIVE") and not can_transition("RENEWED", "ACTIVE")
    assert not can_transition("ACTIVE", "DRAFT")


def test_compute_expiry_incl_leap_day():
    assert compute_expiry(date(2026, 3, 1)) == date(2027, 2, 28)
    assert compute_expiry(date(2028, 2, 29)) == date(2029, 2, 27)


def test_issuance_prerequisites():
    ok = dict(quote_status="ACCEPTED", eligibility_status="ELIGIBLE", decision_outcome="APPROVED",
              acceptance_recorded=True, payment_status="SUCCESS", payment_amount=100.0, premium=100.0)
    assert check_issuance_prerequisites(**ok) == []
    for k, v in [("acceptance_recorded", False), ("payment_status", "FAILED"), ("decision_outcome", "REFERRED"),
                 ("eligibility_status", "INELIGIBLE"), ("payment_amount", 99.0)]:
        assert check_issuance_prerequisites(**{**ok, k: v}), k
    assert check_issuance_prerequisites(**ok, blocking_exceptions=["X"])


def P(pid, start, end, **kw):
    return {"policy_id": pid, "asset_id": "AST-1", "product_id": "PROD-001", "start_date": start, "expiry_date": end,
            "status": "ACTIVE", "cancelled_on": None, "overlap_reason": None, "renewal_of_policy_id": None, **kw}


def test_overlap_detection_with_permitted_reasons():
    a = P("POL-1", date(2026, 1, 1), date(2026, 12, 31))
    assert find_unauthorized_overlaps([a, P("POL-2", date(2026, 6, 1), date(2027, 5, 31))]) == [("POL-1", "POL-2")]
    assert find_unauthorized_overlaps([a, P("POL-2", date(2027, 1, 1), date(2027, 12, 31))]) == []      # adjacent
    assert find_unauthorized_overlaps([a, P("POL-2", date(2026, 6, 1), date(2027, 5, 31), overlap_reason="ADDITIONAL_COVER")]) == []
    assert find_unauthorized_overlaps([a, P("POL-2", date(2026, 6, 1), date(2027, 5, 31), renewal_of_policy_id="POL-1")]) == []
    cancelled = P("POL-0", date(2026, 1, 1), date(2026, 12, 31), status="CANCELLED", cancelled_on=date(2026, 5, 31))
    assert find_unauthorized_overlaps([cancelled, P("POL-3", date(2026, 6, 1), date(2027, 5, 31))]) == []


def test_renewal_eligibility_rules():
    kw = dict(policy_status="ACTIVE", expiry_date=date(2027, 2, 28), today=date(2027, 1, 15), has_cancellation=False,
              pending_payments=0, existing_open_renewal=False)
    assert check_renewal_eligibility(**kw)[0] == []
    assert check_renewal_eligibility(**{**kw, "policy_status": "CANCELLED"})[0]
    assert check_renewal_eligibility(**{**kw, "today": date(2026, 6, 1)})[0]
    assert check_renewal_eligibility(**{**kw, "existing_open_renewal": True})[0]


def test_endorsement_limits():
    assert check_endorsement_limits("PROPERTY", "PROP_BUILDING_PLUS", 250000, 260000) == []
    v = check_endorsement_limits("PROPERTY", "PROP_BUILDING_PLUS", 2500000, 3000000)
    assert any("ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT" in x for x in v)
