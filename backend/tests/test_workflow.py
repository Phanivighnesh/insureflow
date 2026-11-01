from datetime import date, datetime
import pytest
from sqlalchemy import select, func

from app.core.errors import ConflictError, ForbiddenError, ValidationFailed
from app.models import (AuditEvent, Endorsement, Payment, Policy, PolicyStatusHistory, Quote, Renewal,
                        RiskAssessment, UnderwritingDecision, Applicant)
from app.engines.premium_engine import premium_matches, recalculate_from_snapshot
from app.services import workflow as W
from tests.conftest import ADMIN, ANALYST, CUSTOMER, NOW, OTHER_CUSTOMER, REVIEWER, scenario


def submit(session, sid, actor=CUSTOMER, **over):
    q = W.submit_application(session, scenario(sid, **over), actor, NOW)
    session.commit()
    return q


# ---------------------------------------------------------------- scenarios
def test_five_demo_scenarios_produce_engine_outcomes(session):
    got = {sid: submit(session, sid) for sid in
           ["LOW_RISK_AUTO_APPROVE", "MEDIUM_RISK_REFERRAL", "HIGH_RISK_DECLINE", "MISSING_RISK_INFO", "END_TO_END_POLICY"]}
    assert got["LOW_RISK_AUTO_APPROVE"].status == "APPROVED" and got["LOW_RISK_AUTO_APPROVE"].risk_category == "LOW"
    assert got["MEDIUM_RISK_REFERRAL"].status == "REFERRED" and got["MEDIUM_RISK_REFERRAL"].risk_category == "MEDIUM"
    assert got["HIGH_RISK_DECLINE"].status == "DECLINED"
    assert got["MISSING_RISK_INFO"].status == "PENDING_INFORMATION" and got["MISSING_RISK_INFO"].premium is None
    assert got["END_TO_END_POLICY"].status == "APPROVED"
    assert [q.quote_id for q in got.values()] == [f"QTE-2026-00000{i}" for i in range(1, 6)]


def test_submission_persists_all_records_and_audit(session):
    q = submit(session, "LOW_RISK_AUTO_APPROVE")
    assert q.applicant_id == "APP-2026-000001" and q.asset_id == "AST-2026-000001"
    assert session.scalars(select(func.count()).select_from(RiskAssessment)).one() == 1
    d = W.current_decision(session, q.quote_id)
    assert d.decision_id == "UWD-2026-000001" and d.rule_ids == ["UW-APR-001"] and d.decided_by == "SYSTEM"
    types = {e.event_type for e in session.scalars(select(AuditEvent).where(AuditEvent.entity_id == q.quote_id))}
    assert {"QUOTE_SUBMITTED", "ELIGIBILITY_EVALUATED", "RISK_ASSESSED", "PREMIUM_CALCULATED", "UNDERWRITING_DECISION"} <= types


def test_recorded_premium_reconciles_with_independent_recalc(session):
    q = submit(session, "LOW_RISK_AUTO_APPROVE")
    re = recalculate_from_snapshot(q.premium_breakdown, "MOTOR")
    assert premium_matches(float(q.premium), re["final_premium"])
    assert float(q.premium) == 1118.0


def test_validation_errors(session):
    with pytest.raises(ValidationFailed):
        W.submit_application(session, scenario("LOW_RISK_AUTO_APPROVE", product_key="BOAT"), CUSTOMER, NOW)
    p = scenario("LOW_RISK_AUTO_APPROVE")
    p["asset"]["attributes"]["previous_accidents"] = "many"
    with pytest.raises(ValidationFailed):
        W.submit_application(session, p, CUSTOMER, NOW)


# ------------------------------------------------------------ authorization
def test_customer_cannot_access_other_customers_quote(session):
    q = submit(session, "END_TO_END_POLICY")
    with pytest.raises(ForbiddenError):
        W.accept_quote(session, q.quote_id, OTHER_CUSTOMER, NOW)
    assert W.accept_quote(session, q.quote_id, ANALYST, NOW)       # staff allowed


def test_customer_cannot_review(session):
    q = submit(session, "MEDIUM_RISK_REFERRAL")
    with pytest.raises(ForbiddenError):
        W.review_quote(session, q.quote_id, "APPROVE", CUSTOMER, None, NOW)


# --------------------------------------------------------- underwriting review
def test_referred_review_appends_decision_and_keeps_history(session):
    q = submit(session, "MEDIUM_RISK_REFERRAL")
    first = W.current_decision(session, q.quote_id)
    assert first.outcome == "REFERRED" and first.approval_authority == "OPERATIONS_ANALYST"
    W.review_quote(session, q.quote_id, "APPROVE", ANALYST, "Looks fine", NOW)
    session.commit()
    decs = session.scalars(select(UnderwritingDecision).where(UnderwritingDecision.quote_id == q.quote_id)
                           .order_by(UnderwritingDecision.sequence)).all()
    assert [d.outcome for d in decs] == ["REFERRED", "APPROVED"] and decs[1].decision_type == "MANUAL"
    assert decs[0].outcome == "REFERRED"                          # history not overwritten
    assert q.status == "APPROVED"
    with pytest.raises(ConflictError):                            # cannot review twice
        W.review_quote(session, q.quote_id, "REJECT", ANALYST, None, NOW)


def test_authority_enforced_on_review(session):
    p = scenario("LOW_RISK_AUTO_APPROVE")
    p["asset"]["attributes"]["previous_claims"] = 3               # exception rule -> RISK_REVIEWER
    q = W.submit_application(session, p, CUSTOMER, NOW)
    assert q.status == "REFERRED" and W.current_decision(session, q.quote_id).approval_authority == "RISK_REVIEWER"
    with pytest.raises(ForbiddenError):
        W.review_quote(session, q.quote_id, "APPROVE", ANALYST, None, NOW)
    assert W.review_quote(session, q.quote_id, "APPROVE", REVIEWER, None, NOW).outcome == "APPROVED"


def test_reject_and_request_information(session):
    q = submit(session, "MEDIUM_RISK_REFERRAL")
    assert W.review_quote(session, q.quote_id, "REQUEST_INFORMATION", ANALYST, "need survey", NOW).outcome == "PENDING_INFORMATION"
    q2 = submit(session, "MEDIUM_RISK_REFERRAL", applicant={"full_name": "Other", "email": "o@x.test", "age": 40})
    assert W.review_quote(session, q2.quote_id, "REJECT", ANALYST, "no", NOW).outcome == "DECLINED"


def test_provide_information_reevaluates(session):
    q = submit(session, "MISSING_RISK_INFO")
    W.provide_information(session, q.quote_id, {"attributes": {"fire_exposure": "LOW"}}, CUSTOMER, NOW)
    session.commit()
    assert q.eligibility_status == "ELIGIBLE" and q.premium is not None and q.status in ("APPROVED", "REFERRED")
    assert session.scalars(select(func.count()).select_from(UnderwritingDecision)
                           .where(UnderwritingDecision.quote_id == q.quote_id)).one() == 2


# ------------------------------------------------------------- policy issuance
def journey(session, sid="END_TO_END_POLICY"):
    q = submit(session, sid)
    W.accept_quote(session, q.quote_id, CUSTOMER, NOW)
    pay, pol, dup = W.demo_payment(session, q.quote_id, "SUCCESS", CUSTOMER, "idem-1", NOW)
    session.commit()
    return q, pay, pol


def test_full_customer_journey_issues_policy(session):
    q, pay, pol = journey(session)
    assert pol.policy_id == "POL-2026-000001" and pol.status == "ACTIVE" and q.status == "POLICY_ISSUED"
    assert pol.start_date == date(2026, 3, 1) and pol.expiry_date == date(2027, 2, 28)
    assert pay.policy_id == pol.policy_id and pay.is_demo and float(pay.amount) == float(q.premium)
    assert pol.snapshot["decision_id"] and pol.snapshot["acceptance_id"]
    hist = session.scalars(select(PolicyStatusHistory).where(PolicyStatusHistory.policy_id == pol.policy_id)).all()
    assert [(h.from_status, h.to_status) for h in hist] == [(None, "ACTIVE")]


def test_cannot_accept_non_approved_quotes(session):
    for sid in ("MEDIUM_RISK_REFERRAL", "HIGH_RISK_DECLINE", "MISSING_RISK_INFO"):
        q = submit(session, sid, applicant={"full_name": sid, "email": sid.lower() + "@x.test", "age": 40,
                                            "location": "Riverton"} if False else scenario(sid)["applicant"])
        with pytest.raises(ConflictError):
            W.accept_quote(session, q.quote_id, CUSTOMER, NOW)


def test_failed_and_pending_payment_do_not_issue_policy(session):
    q = submit(session, "END_TO_END_POLICY")
    W.accept_quote(session, q.quote_id, CUSTOMER, NOW)
    pay, pol, _ = W.demo_payment(session, q.quote_id, "FAILED", CUSTOMER, None, NOW)
    assert pol is None and q.status == "ACCEPTED"
    pay2, pol, _ = W.demo_payment(session, q.quote_id, "PENDING", CUSTOMER, None, NOW)
    assert pol is None
    with pytest.raises(ConflictError):                            # pending must be resolved first
        W.demo_payment(session, q.quote_id, "SUCCESS", CUSTOMER, None, NOW)
    pay2, pol = W.resolve_pending_payment(session, pay2.payment_id, "SUCCESS", CUSTOMER, NOW)
    assert pol is not None and pol.status == "ACTIVE"


def test_issue_without_acceptance_or_payment_rejected(session):
    q = submit(session, "END_TO_END_POLICY")
    with pytest.raises(ConflictError) as e:
        W.issue_policy(session, q.quote_id, ADMIN, NOW)
    assert any("acceptance" in d.lower() for d in e.value.details)
    assert any("payment" in d.lower() for d in e.value.details)


def test_duplicate_payment_idempotent_and_no_duplicate_policy(session):
    q, pay, pol = journey(session)
    pay2, pol2, dup = W.demo_payment(session, q.quote_id, "SUCCESS", CUSTOMER, "idem-1", NOW)
    assert dup and pay2.payment_id == pay.payment_id and pol2.policy_id == pol.policy_id
    assert session.scalars(select(func.count()).select_from(Policy)).one() == 1
    with pytest.raises(ConflictError):
        W.accept_quote(session, q.quote_id, CUSTOMER, NOW)        # already accepted


def test_overlapping_policy_blocked_unless_justified(session):
    q, _, pol = journey(session)
    # second identical application on the same asset: new asset row => different asset, so no overlap
    q2 = submit(session, "END_TO_END_POLICY")
    assert q2.asset_id != q.asset_id
    # force same asset to prove the blocking rule
    q2.asset_id = q.asset_id
    W.accept_quote(session, q2.quote_id, CUSTOMER, NOW)
    with pytest.raises(ConflictError) as e:
        W.demo_payment(session, q2.quote_id, "SUCCESS", CUSTOMER, None, NOW)
    assert any("UNAUTHORIZED_POLICY_OVERLAP" in d for d in e.value.details)


# ------------------------------------------------------------ cancel/endorse
def test_cancellation_and_invalid_transitions(session):
    _, _, pol = journey(session)
    with pytest.raises(ValidationFailed):
        W.cancel_policy(session, pol.policy_id, "", CUSTOMER, NOW)
    W.cancel_policy(session, pol.policy_id, "Sold vehicle", CUSTOMER, NOW)
    assert pol.status == "CANCELLED" and pol.cancelled_at == date(2026, 3, 1)
    with pytest.raises(ConflictError):
        W.cancel_policy(session, pol.policy_id, "again", CUSTOMER, NOW)


def test_endorsement_valid_flow_preserves_original(session):
    _, _, pol = journey(session)
    e = W.request_endorsement(session, pol.policy_id, {"endorsement_type": "COVERAGE_ADJUSTMENT",
                              "new_coverage_amount": 210000}, date(2026, 6, 1), CUSTOMER, NOW)
    assert e.endorsement_id == f"END-{pol.policy_id}-001" and e.status == "PENDING" and e.premium_after > e.premium_before
    W.decide_endorsement(session, e.endorsement_id, True, ANALYST, "ok", NOW)
    assert e.status == "APPROVED"
    assert float(pol.coverage_amount) == 200000                    # original untouched
    assert W.effective_terms(session, pol)[0] == 210000
    assert pol.snapshot["coverage_amount"] == 200000


def test_endorsement_exceeding_product_limit_auto_rejected(session):
    _, _, pol = journey(session)
    e = W.request_endorsement(session, pol.policy_id, {"endorsement_type": "COVERAGE_ADJUSTMENT",
                              "new_coverage_amount": 2500000, "new_declared_value": 3000000}, date(2026, 6, 1), CUSTOMER, NOW)
    assert e.status == "REJECTED" and "ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT" in e.decision_reason and e.premium_after is None


def test_endorsement_authority_and_date_validation(session):
    _, _, pol = journey(session)
    with pytest.raises(ValidationFailed):
        W.request_endorsement(session, pol.policy_id, {"endorsement_type": "COVERAGE_ADJUSTMENT", "new_coverage_amount": 210000},
                              date(2030, 1, 1), CUSTOMER, NOW)
    e = W.request_endorsement(session, pol.policy_id, {"endorsement_type": "COVERAGE_ADJUSTMENT",
                              "new_coverage_amount": 600000, "new_declared_value": 650000}, date(2026, 6, 1), CUSTOMER, NOW)
    assert e.status == "PENDING"
    with pytest.raises(ForbiddenError):                            # 600k > analyst limit 500k
        W.decide_endorsement(session, e.endorsement_id, True, ANALYST, None, NOW)
    assert W.decide_endorsement(session, e.endorsement_id, True, REVIEWER, None, NOW).status == "APPROVED"


# ------------------------------------------------------------------- renewals
TODAY = date(2027, 1, 15)


def test_renewal_offer_accept_creates_new_policy_no_overlap(session):
    _, _, pol = journey(session)
    ren = W.generate_renewal(session, pol.policy_id, CUSTOMER, TODAY, NOW)
    assert ren.renewal_id == f"REN-{pol.policy_id}-2027" and ren.status == "OFFERED"
    assert ren.new_start_date == date(2027, 3, 1) and ren.offered_premium is not None
    ren, new = W.respond_renewal(session, ren.renewal_id, True, CUSTOMER, "SUCCESS", None, NOW)
    session.commit()
    assert ren.status == "ACCEPTED" and new.renewal_of_policy_id == pol.policy_id and new.status == "ACTIVE"
    assert pol.status == "RENEWED"
    with pytest.raises(ConflictError):
        W.generate_renewal(session, pol.policy_id, CUSTOMER, TODAY, NOW)   # RENEWED not renewable


def test_renewal_decline_and_duplicate(session):
    _, _, pol = journey(session)
    ren = W.generate_renewal(session, pol.policy_id, CUSTOMER, TODAY, NOW)
    with pytest.raises(ConflictError):
        W.generate_renewal(session, pol.policy_id, CUSTOMER, TODAY, NOW)
    ren, _ = W.respond_renewal(session, ren.renewal_id, False, CUSTOMER, reason="Switching insurer", now=NOW)
    assert ren.status == "DECLINED" and pol.status == "ACTIVE"


def test_renewal_for_cancelled_policy_refused(session):
    _, _, pol = journey(session)
    W.cancel_policy(session, pol.policy_id, "Customer request", CUSTOMER, NOW)
    with pytest.raises(ConflictError) as e:
        W.generate_renewal(session, pol.policy_id, CUSTOMER, TODAY, NOW)
    assert any("RENEWAL_FOR_CANCELLED_POLICY" in d for d in e.value.details)
    assert session.scalars(select(func.count()).select_from(Renewal)).one() == 0


def test_renewal_outside_window_refused(session):
    _, _, pol = journey(session)
    with pytest.raises(ConflictError):
        W.generate_renewal(session, pol.policy_id, CUSTOMER, date(2026, 6, 1), NOW)


def test_cancelling_policy_withdraws_open_renewal(session):
    _, _, pol = journey(session)
    ren = W.generate_renewal(session, pol.policy_id, CUSTOMER, TODAY, NOW)
    W.cancel_policy(session, pol.policy_id, "x", CUSTOMER, NOW)
    assert ren.status == "CANCELLED"


def test_renewal_failed_payment_keeps_offer_open(session):
    _, _, pol = journey(session)
    ren = W.generate_renewal(session, pol.policy_id, CUSTOMER, TODAY, NOW)
    ren, new = W.respond_renewal(session, ren.renewal_id, True, CUSTOMER, "FAILED", None, NOW)
    assert new is None and ren.status == "OFFERED" and pol.status == "ACTIVE"


def test_expire_policies(session):
    _, _, pol = journey(session)
    assert W.expire_policies(session, date(2027, 3, 1), now=NOW) == 1 and pol.status == "EXPIRED"


# ------------------------------------------------------------ integrity
def test_foreign_keys_enforced(session):
    from sqlalchemy.exc import IntegrityError
    from app.models import InsuredAsset
    session.add(InsuredAsset(asset_id="AST-X", applicant_id="APP-NOPE", asset_type="VEHICLE", attributes={}, created_at=NOW))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_applicant_reuse_by_email_within_owner(session):
    a = submit(session, "LOW_RISK_AUTO_APPROVE")
    b = submit(session, "LOW_RISK_AUTO_APPROVE")
    assert a.applicant_id == b.applicant_id and a.asset_id != b.asset_id
    c = submit(session, "LOW_RISK_AUTO_APPROVE", actor=OTHER_CUSTOMER)
    assert c.applicant_id != a.applicant_id                         # isolated per customer key


def test_provide_information_derives_year_built_from_property_age(session):
    """Integration bug found while building the portal form: property age supplied later must resolve the quote."""
    p = scenario("END_TO_END_POLICY")
    del p["asset"]["attributes"]["property_age_years"]
    q = W.submit_application(session, p, CUSTOMER, NOW)
    assert q.status == "PENDING_INFORMATION" and "asset_age_years" in q.eligibility_detail["missing_fields"]
    W.provide_information(session, q.quote_id, {"attributes": {"property_age_years": 5}}, CUSTOMER, NOW)
    assert q.eligibility_status == "ELIGIBLE" and q.status == "APPROVED" and q.premium is not None
