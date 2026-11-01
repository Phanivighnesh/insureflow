"""End-to-end CLI demonstration against a real SQLite file (no API needed yet).
Run:  python -m scripts.run_demo
Every number printed is produced by the deterministic engines; nothing is hard-coded."""
from __future__ import annotations
import os
from datetime import date, datetime

from app.core.security import Actor
from app.database.session import init_db, make_engine, make_session_factory
from app.services import workflow as W
from app.services.demo_scenarios import SCENARIOS
from app.services.seed import seed_master_data

DB = "insureflow_demo.db"
NOW = datetime(2026, 10, 30, 9, 0, 0)


def main():
    if os.path.exists(DB):
        os.remove(DB)
    engine = make_engine(f"sqlite:///./{DB}")
    init_db(engine)
    s = make_session_factory(engine)()
    seed_master_data(s)
    cust, analyst = Actor("demo-customer", "CUSTOMER", "demo-key"), Actor("demo-analyst", "OPERATIONS_ANALYST")
    quotes = {}
    print(f"{'SCENARIO':26} {'QUOTE':16} {'ELIGIBILITY':18} {'RISK':>6} {'CAT':7} {'PREMIUM':>10}  OUTCOME / AUTHORITY")
    for sc in SCENARIOS:
        q = W.submit_application(s, sc["payload"], cust, NOW)
        d = W.current_decision(s, q.quote_id)
        quotes[sc["id"]] = q
        print(f"{sc['id']:26} {q.quote_id:16} {q.eligibility_status:18} {q.risk_score:6.2f} {q.risk_category:7} "
              f"{(float(q.premium) if q.premium else 0):10.2f}  {d.outcome} / {d.approval_authority}")
    s.commit()

    print("\n-- Analyst reviews the referred medium-risk quote")
    q = quotes["MEDIUM_RISK_REFERRAL"]
    print("   ", W.review_quote(s, q.quote_id, "APPROVE", analyst, "Survey satisfactory", NOW).outcome)

    print("-- Customer journey: accept -> demo payment (FAILED, then SUCCESS) -> policy")
    q = quotes["END_TO_END_POLICY"]
    W.accept_quote(s, q.quote_id, cust, NOW)
    p1, pol, _ = W.demo_payment(s, q.quote_id, "FAILED", cust, None, NOW)
    print(f"    payment {p1.payment_id}: {p1.status}, policy issued: {pol is not None}")
    p2, pol, _ = W.demo_payment(s, q.quote_id, "SUCCESS", cust, "demo-1", NOW)
    print(f"    payment {p2.payment_id}: {p2.status}, policy {pol.policy_id} {pol.status} {pol.start_date}..{pol.expiry_date}")
    e = W.request_endorsement(s, pol.policy_id, {"endorsement_type": "COVERAGE_ADJUSTMENT",
                              "new_coverage_amount": 2500000, "new_declared_value": 3000000}, date(2026, 12, 1), cust, NOW)
    print(f"-- Endorsement {e.endorsement_id}: {e.status} ({e.decision_reason[:70]}...)")
    ren = W.generate_renewal(s, pol.policy_id, cust, date(2027, 9, 15), NOW)
    print(f"-- Renewal {ren.renewal_id}: {ren.status}, offered premium {float(ren.offered_premium):.2f}")
    s.commit()
    print(f"\nDatabase written to ./{DB}")


if __name__ == "__main__":
    main()
