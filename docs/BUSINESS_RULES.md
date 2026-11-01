# BUSINESS RULES (generated from `backend/app/core/rules_config.py`)

> **Illustrative synthetic demonstration rules - not real insurer underwriting policy.**  
> Rules version `RULES-1.0.0` | Premium formula `PREM-1.0.0` | Underwriting engine `UW-1.0.0` | Currency `USD`

Regenerate with: `cd backend && python -m scripts.generate_business_rules_doc > ../docs/BUSINESS_RULES.md`

## 1. Decision pipeline

1. Build context from applicant + asset + requested cover (asset age derived from year of manufacture/build).
2. **Eligibility** (ELG-001..008): ELIGIBLE / INELIGIBLE (any blocking check fails) / NEEDS_INFORMATION (only mandatory fields missing). INELIGIBLE takes precedence.
3. **Risk** weighted score 0-100. Missing/unrecognised inputs get a penalty score, never 0.
4. **Premium** (only when ELIGIBLE): `round2(coverage x base_rate x coverage_multiplier x age x location x claims x risk) + fixed charges` (Decimal, HALF_UP).
5. **Underwriting decision** (rule IDs below). Every decision is a new immutable row.

## 2. Global thresholds

| Parameter | Value |
|---|---|
| Risk LOW max | 30 |
| Risk MEDIUM max (above = HIGH) | 70 |
| Auto-decline at risk score >= | 85.0 |
| Missing-input risk penalty | 60.0 |
| Unknown-claims premium factor | 1.1 |
| Premium reconciliation tolerance | 0.01 |
| Quote validity (days) | 30 |
| Renewal window (days before expiry) | 60 |
| Max coverage / declared value | 1.0 |

## 3. Underwriting rule IDs

| Rule | Meaning |
|---|---|
| UW-APR-001 | Auto-approve: LOW risk and coverage <= auto-approval limit |
| UW-REF-RISK | Referral: risk category requires analyst (MEDIUM) or senior (HIGH) authority |
| UW-REF-COV | Referral: coverage above auto-approval limit; authority by coverage band |
| UW-REF-CLAIMS | Referral: >=3 prior claims -> at least RISK_REVIEWER |
| UW-DEC-001 | Decline: ineligible (failed blocking eligibility checks) |
| UW-DEC-002 | Decline: risk score >= decline threshold |
| UW-PEN-001 | Pending information: mandatory fields missing |
| UW-MAN-APR/REJ/INF | Manual approve / reject / request-information by an authorised reviewer |

Required authority = highest of {risk-category level, coverage-band level, exception-rule level}.

| Role | Highest authority exercisable |
|---|---|
| CUSTOMER | - (customer) |
| OPERATIONS_ANALYST | OPERATIONS_ANALYST |
| RISK_REVIEWER | RISK_REVIEWER |
| ADMINISTRATOR | SENIOR_UNDERWRITER |

## 4. Coverage options

| ID | Code | Product | Name | Min limit | Max limit | Rate multiplier |
|---|---|---|---|---|---|---|
| COV-001 | MOTOR_THEFT_FIRE | MOTOR | Theft & Fire | 2,000 | 150,000 | 0.6 |
| COV-002 | MOTOR_COMPREHENSIVE | MOTOR | Comprehensive | 2,000 | 150,000 | 1.0 |
| COV-003 | MOTOR_COMPREHENSIVE_PLUS | MOTOR | Comprehensive Plus | 5,000 | 150,000 | 1.25 |
| COV-004 | PROP_BUILDING_BASIC | PROPERTY | Building Basic | 50,000 | 2,000,000 | 0.8 |
| COV-005 | PROP_BUILDING_PLUS | PROPERTY | Building Plus (incl. flood) | 50,000 | 2,000,000 | 1.0 |
| COV-006 | PROP_BUILDING_CONTENTS | PROPERTY | Building & Contents | 50,000 | 2,000,000 | 1.2 |
| COV-007 | COMM_PROPERTY_ONLY | COMMERCIAL | Property Only | 50,000 | 3,000,000 | 0.9 |
| COV-008 | COMM_PROPERTY_BI | COMMERCIAL | Property + Business Interruption | 50,000 | 3,000,000 | 1.15 |
| COV-009 | COMM_ALL_RISKS | COMMERCIAL | All Risks | 100,000 | 3,000,000 | 1.4 |

## 5.1 Motor Insurance (`PROD-001`)

- Base rate: **0.04**; insured value 2,000-150,000; applicant age 18-80; max asset age: 20
- Fixed charges: {'policy_fee': 25.0, 'stamp_duty': 10.0}
- Authority limits (coverage): auto <= 40,000; analyst <= 75,000; risk reviewer <= 120,000; above = senior underwriter
- Mandatory fields: `applicant_age, declared_value, requested_coverage, coverage_code, location, vehicle_type, asset_age_years, registration_location, previous_accidents`
- Allowed values: {'vehicle_type': ['HATCHBACK', 'SEDAN', 'SUV', 'TRUCK', 'MOTORCYCLE', 'SPORTS']}
- Age factor bands: [(0, 3, 0.95), (4, 8, 1.0), (9, 14, 1.2), (15, 999, 1.45)]
- Location factor: {'LOW': 0.95, 'MEDIUM': 1.0, 'HIGH': 1.25}

| Risk factor | Input | Weight | Mandatory | Scoring |
|---|---|---|---|---|
| RSK-001 Previous accidents | `previous_accidents` | 0.3 | True | {'bands': [(0, 0, 5), (1, 1, 40), (2, 2, 70), (3, 999, 100)]} |
| RSK-002 Vehicle age (years) | `asset_age_years` | 0.15 | True | {'bands': [(0, 3, 10), (4, 8, 25), (9, 14, 55), (15, 999, 85)]} |
| RSK-003 Geographic risk tier | `location_tier` | 0.2 | True | {'map': {'LOW': 10, 'MEDIUM': 40, 'HIGH': 85}} |
| RSK-004 Previous claims | `previous_claims` | 0.2 | False | {'bands': [(0, 0, 5), (1, 1, 40), (2, 2, 70), (3, 999, 100)]} |
| RSK-005 Vehicle type | `vehicle_type` | 0.15 | True | {'map': {'HATCHBACK': 20, 'SEDAN': 25, 'SUV': 35, 'TRUCK': 45, 'MOTORCYCLE': 60, 'SPORTS': 80}} |

## 5.2 Property Insurance (`PROD-002`)

- Base rate: **0.0035**; insured value 50,000-2,000,000; applicant age 18-85; max asset age: 100
- Fixed charges: {'policy_fee': 40.0, 'stamp_duty': 15.0}
- Authority limits (coverage): auto <= 250,000; analyst <= 500,000; risk reviewer <= 1,000,000; above = senior underwriter
- Mandatory fields: `applicant_age, declared_value, requested_coverage, coverage_code, location, property_type, construction_type, asset_age_years, flood_exposure, fire_exposure`
- Allowed values: {'property_type': ['HOUSE', 'APARTMENT', 'TOWNHOUSE', 'VILLA'], 'construction_type': ['CONCRETE', 'MASONRY', 'STEEL', 'MIXED', 'TIMBER'], 'flood_exposure': ['NONE', 'LOW', 'MODERATE', 'HIGH'], 'fire_exposure': ['NONE', 'LOW', 'MODERATE', 'HIGH']}
- Age factor bands: [(0, 10, 0.95), (11, 30, 1.0), (31, 60, 1.2), (61, 999, 1.5)]
- Location factor: {'LOW': 0.95, 'MEDIUM': 1.0, 'HIGH': 1.35}

| Risk factor | Input | Weight | Mandatory | Scoring |
|---|---|---|---|---|
| RSK-006 Flood exposure | `flood_exposure` | 0.25 | True | {'map': {'NONE': 0, 'LOW': 20, 'MODERATE': 55, 'HIGH': 95}} |
| RSK-007 Fire exposure | `fire_exposure` | 0.2 | True | {'map': {'NONE': 0, 'LOW': 20, 'MODERATE': 55, 'HIGH': 95}} |
| RSK-008 Building age (years) | `asset_age_years` | 0.15 | True | {'bands': [(0, 10, 10), (11, 30, 30), (31, 60, 60), (61, 999, 85)]} |
| RSK-009 Construction material | `construction_type` | 0.2 | True | {'map': {'CONCRETE': 10, 'STEEL': 15, 'MASONRY': 15, 'MIXED': 40, 'TIMBER': 70}} |
| RSK-010 Geographic risk tier | `location_tier` | 0.1 | True | {'map': {'LOW': 10, 'MEDIUM': 40, 'HIGH': 85}} |
| RSK-011 Previous claims | `previous_claims` | 0.1 | False | {'bands': [(0, 0, 5), (1, 1, 40), (2, 2, 70), (3, 999, 100)]} |

## 5.3 Commercial Insurance (`PROD-003`)

- Base rate: **0.006**; insured value 50,000-3,000,000; applicant age 18-85; max asset age: None
- Fixed charges: {'policy_fee': 60.0, 'stamp_duty': 20.0}
- Authority limits (coverage): auto <= 300,000; analyst <= 750,000; risk reviewer <= 1,500,000; above = senior underwriter
- Mandatory fields: `applicant_age, declared_value, requested_coverage, coverage_code, location, business_category, industry_hazard_class, fire_exposure`
- Allowed values: {'business_category': ['OFFICE_SERVICES', 'RETAIL', 'HOSPITALITY', 'LOGISTICS', 'MANUFACTURING', 'CONSTRUCTION'], 'industry_hazard_class': ['LOW', 'MODERATE', 'HIGH'], 'fire_exposure': ['NONE', 'LOW', 'MODERATE', 'HIGH']}
- Age factor bands: None
- Location factor: {'LOW': 0.95, 'MEDIUM': 1.0, 'HIGH': 1.3}

| Risk factor | Input | Weight | Mandatory | Scoring |
|---|---|---|---|---|
| RSK-012 Industry hazard class | `industry_hazard_class` | 0.3 | True | {'map': {'LOW': 15, 'MODERATE': 50, 'HIGH': 85}} |
| RSK-013 Fire exposure | `fire_exposure` | 0.2 | True | {'map': {'NONE': 0, 'LOW': 20, 'MODERATE': 55, 'HIGH': 95}} |
| RSK-014 Number of insured locations | `number_of_locations` | 0.15 | False | {'bands': [(1, 1, 80), (2, 3, 45), (4, 999, 20)]} |
| RSK-015 Business category | `business_category` | 0.15 | True | {'map': {'OFFICE_SERVICES': 15, 'RETAIL': 35, 'HOSPITALITY': 50, 'LOGISTICS': 55, 'MANUFACTURING': 65, 'CONSTRUCTION': 75}} |
| RSK-016 Geographic risk tier | `location_tier` | 0.1 | True | {'map': {'LOW': 10, 'MEDIUM': 40, 'HIGH': 85}} |
| RSK-017 Previous claims | `previous_claims` | 0.1 | False | {'bands': [(0, 0, 5), (1, 1, 40), (2, 2, 70), (3, 999, 100)]} |

## 6. Shared factor tables

- Claims factor bands: [(0, 0, 1.0), (1, 1, 1.15), (2, 2, 1.35), (3, 999, 1.7)]
- Risk-category factor: {'LOW': 1.0, 'MEDIUM': 1.15, 'HIGH': 1.4}
- Location tiers: {'Alderbrook': 'LOW', 'Hillcrest': 'LOW', 'Maplewood': 'LOW', 'Riverton': 'MEDIUM', 'Lakeside': 'MEDIUM', 'Fairview': 'MEDIUM', 'Harborview': 'HIGH', 'Deltaport': 'HIGH', 'Stormvale': 'HIGH'}
- Exposure scores: {'NONE': 0, 'LOW': 20, 'MODERATE': 55, 'HIGH': 95}
- Count bands (accidents/claims): [(0, 0, 5), (1, 1, 40), (2, 2, 70), (3, 999, 100)]

## 7. Lifecycle and exception rules

- Policy states: DRAFT, PENDING_ACCEPTANCE, PENDING_PAYMENT, ACTIVE, CANCELLED, EXPIRED, RENEWED. Policy rows are created only at issuance (ACTIVE); pre-issuance stages are tracked on the Quote (APPROVED -> ACCEPTED -> POLICY_ISSUED).
- Issuance requires: ELIGIBLE + current decision APPROVED + acceptance + SUCCESS payment equal to premium + no blocking exception (e.g. unauthorised overlap, duplicate issuance).
- Overlap is permitted only with a justification (`overlap_reason`) or a renewal chain link; cancelled policies end at the cancellation date.
- Endorsements never overwrite the policy: effective terms = latest APPROVED endorsement. Limit breaches are auto-REJECTED with `ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT`. Approval authority by new coverage band.
- Renewals: only ACTIVE, non-cancelled policies inside the window; underwriting-ineligible renewals are recorded as CANCELLED with reasons; cancelled policies raise `RENEWAL_FOR_CANCELLED_POLICY`.
