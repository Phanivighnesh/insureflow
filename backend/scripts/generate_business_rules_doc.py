"""Regenerates docs/BUSINESS_RULES.md tables directly from app/core/rules_config.py (no drift)."""
from app.core import rules_config as R

L = []
a = L.append
a("# BUSINESS RULES (generated from `backend/app/core/rules_config.py`)\n")
a(f"> **Illustrative synthetic demonstration rules - not real insurer underwriting policy.**  ")
a(f"> Rules version `{R.RULES_VERSION}` | Premium formula `{R.PREMIUM_FORMULA_VERSION}` | Underwriting engine `{R.UW_ENGINE_VERSION}` | Currency `{R.CURRENCY}`\n")
a("Regenerate with: `cd backend && python -m scripts.generate_business_rules_doc > ../docs/BUSINESS_RULES.md`\n")
a("## 1. Decision pipeline\n")
a("1. Build context from applicant + asset + requested cover (asset age derived from year of manufacture/build).")
a("2. **Eligibility** (ELG-001..008): ELIGIBLE / INELIGIBLE (any blocking check fails) / NEEDS_INFORMATION (only mandatory fields missing). INELIGIBLE takes precedence.")
a("3. **Risk** weighted score 0-100. Missing/unrecognised inputs get a penalty score, never 0.")
a("4. **Premium** (only when ELIGIBLE): `round2(coverage x base_rate x coverage_multiplier x age x location x claims x risk) + fixed charges` (Decimal, HALF_UP).")
a("5. **Underwriting decision** (rule IDs below). Every decision is a new immutable row.\n")
a("## 2. Global thresholds\n")
a("| Parameter | Value |\n|---|---|")
for k, v in [("Risk LOW max", R.RISK_THRESHOLDS["low_max"]), ("Risk MEDIUM max (above = HIGH)", R.RISK_THRESHOLDS["medium_max"]),
             ("Auto-decline at risk score >=", R.DECLINE_RISK_SCORE), ("Missing-input risk penalty", R.MISSING_RISK_PENALTY),
             ("Unknown-claims premium factor", R.UNKNOWN_CLAIMS_FACTOR), ("Premium reconciliation tolerance", R.PREMIUM_TOLERANCE),
             ("Quote validity (days)", R.QUOTE_VALIDITY_DAYS), ("Renewal window (days before expiry)", R.RENEWAL_WINDOW_DAYS),
             ("Max coverage / declared value", R.MAX_COVERAGE_TO_VALUE_RATIO)]:
    a(f"| {k} | {v} |")
a("\n## 3. Underwriting rule IDs\n")
a("| Rule | Meaning |\n|---|---|")
for r, m in [("UW-APR-001", "Auto-approve: LOW risk and coverage <= auto-approval limit"),
             ("UW-REF-RISK", "Referral: risk category requires analyst (MEDIUM) or senior (HIGH) authority"),
             ("UW-REF-COV", "Referral: coverage above auto-approval limit; authority by coverage band"),
             ("UW-REF-CLAIMS", "Referral: >=3 prior claims -> at least RISK_REVIEWER"),
             ("UW-DEC-001", "Decline: ineligible (failed blocking eligibility checks)"),
             ("UW-DEC-002", "Decline: risk score >= decline threshold"),
             ("UW-PEN-001", "Pending information: mandatory fields missing"),
             ("UW-MAN-APR/REJ/INF", "Manual approve / reject / request-information by an authorised reviewer")]:
    a(f"| {r} | {m} |")
a("\nRequired authority = highest of {risk-category level, coverage-band level, exception-rule level}.\n")
a("| Role | Highest authority exercisable |\n|---|---|")
for k, v in R.ROLE_AUTHORITY.items():
    a(f"| {k} | {v or '- (customer)'} |")
a("\n## 4. Coverage options\n")
a("| ID | Code | Product | Name | Min limit | Max limit | Rate multiplier |\n|---|---|---|---|---|---|---|")
for c in R.COVERAGE_OPTIONS:
    a(f"| {c['coverage_id']} | {c['code']} | {c['product_key']} | {c['name']} | {c['min_limit']:,} | {c['max_limit']:,} | {c['rate_multiplier']} |")
for key, p in R.PRODUCTS.items():
    a(f"\n## 5.{list(R.PRODUCTS).index(key)+1} {p['name']} (`{p['product_id']}`)\n")
    a(f"- Base rate: **{p['base_rate']}**; insured value {p['insured_value'][0]:,}-{p['insured_value'][1]:,}; applicant age {p['applicant_age'][0]}-{p['applicant_age'][1]}; max asset age: {p['max_asset_age']}")
    a(f"- Fixed charges: {p['fixed_charges']}")
    a(f"- Authority limits (coverage): auto <= {p['auto_approval_limit']:,}; analyst <= {p['analyst_limit']:,}; risk reviewer <= {p['reviewer_limit']:,}; above = senior underwriter")
    a(f"- Mandatory fields: `{', '.join(p['mandatory'])}`")
    a(f"- Allowed values: {p['allowed_values']}")
    a(f"- Age factor bands: {p['age_factor']}")
    a(f"- Location factor: {p['location_factor']}\n")
    a("| Risk factor | Input | Weight | Mandatory | Scoring |\n|---|---|---|---|---|")
    for f in p["risk_factors"]:
        a(f"| {f['rsk_id']} {f['label']} | `{f['input']}` | {f['weight']} | {f['mandatory']} | {f['scorer']} |")
a("\n## 6. Shared factor tables\n")
a(f"- Claims factor bands: {R.CLAIMS_FACTOR}\n- Risk-category factor: {R.RISK_CATEGORY_FACTOR}\n- Location tiers: {R.LOCATION_RISK_TIER}\n- Exposure scores: {R.EXPOSURE_SCORE}\n- Count bands (accidents/claims): {R.COUNT_BANDS}")
a("\n## 7. Lifecycle and exception rules\n")
a("- Policy states: DRAFT, PENDING_ACCEPTANCE, PENDING_PAYMENT, ACTIVE, CANCELLED, EXPIRED, RENEWED. Policy rows are created only at issuance (ACTIVE); pre-issuance stages are tracked on the Quote (APPROVED -> ACCEPTED -> POLICY_ISSUED).")
a("- Issuance requires: ELIGIBLE + current decision APPROVED + acceptance + SUCCESS payment equal to premium + no blocking exception (e.g. unauthorised overlap, duplicate issuance).")
a("- Overlap is permitted only with a justification (`overlap_reason`) or a renewal chain link; cancelled policies end at the cancellation date.")
a("- Endorsements never overwrite the policy: effective terms = latest APPROVED endorsement. Limit breaches are auto-REJECTED with `ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT`. Approval authority by new coverage band.")
a("- Renewals: only ACTIVE, non-cancelled policies inside the window; underwriting-ineligible renewals are recorded as CANCELLED with reasons; cancelled policies raise `RENEWAL_FOR_CANCELLED_POLICY`.")
print("\n".join(L))
