# VALIDATION REPORT - `full` dataset (seed 20261022)

_Rendered from `data/exports/full/validation_report.json`. Generated 2026-10-31T05:26:11 by generator 1.0.0._

> 100% synthetic data. No real customer information and no external datasets were used.

## Row counts

| Table | Rows |
|---|---|
| applicants | 3,000 |
| approval_authorities | 12 |
| audit_events | 34,498 |
| coverage_options | 9 |
| endorsements | 193 |
| id_counters | 197 |
| insured_assets | 4,000 |
| payments | 2,584 |
| policies | 2,000 |
| policy_coverages | 2,000 |
| policy_status_history | 3,285 |
| product_coverages | 9 |
| products | 3 |
| quote_acceptances | 2,283 |
| quote_coverages | 4,000 |
| quotes | 4,000 |
| renewals | 1,200 |
| risk_assessments | 4,128 |
| risk_factors | 17 |
| underwriting_decisions | 6,247 |

## Validation checks (independent detector - never reads ground truth)

| Check | Records checked | Failed |
|---|---|---|
| allowed_enumerations | 16,224 | 0 |
| coverage_limits | 2,147 | 20 |
| date_ordering | 13,435 | 10 |
| duplicate_applicants | 3,000 | 0 |
| duplicate_payments | 2,000 | 10 |
| foreign_key_integrity | 63,977 | 10 |
| lifecycle_transitions | 2,000 | 0 |
| policy_issuance_conditions | 2,000 | 20 |
| policy_overlaps | 2,000 | 20 |
| premium_reconciliation | 6,815 | 34 |
| quote_progression | 3,026 | 0 |
| renewal_eligibility | 1,200 | 20 |

## Metrics

| Metric | Value |
|---|---|
| total_records_processed | 23224 |
| valid_records | 23094 |
| invalid_records | 130 |
| exception_total | 130 |
| eligibility_pass_rate | 0.9087 |
| approval_rate | 0.7565 |
| rejection_rate | 0.1598 |
| referral_rate | 0.5272 |
| pending_information_rate | 0.0663 |
| average_premium | 1554.9 |
| premium_reconciliation_accuracy | 0.995 |
| policy_issuance_compliance | 0.99 |
| renewal_eligibility_compliance | 0.9833 |
| foreign_key_integrity | 0.9998 |

### Exceptions detected by type

| Issue type | Count |
|---|---|
| DUPLICATE_TRANSACTION | 10 |
| ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT | 20 |
| INVALID_DATE_SEQUENCE | 10 |
| INVALID_FOREIGN_KEY | 10 |
| POLICY_WITHOUT_ACCEPTANCE | 20 |
| PREMIUM_FORMULA_MISMATCH | 20 |
| RENEWAL_FOR_CANCELLED_POLICY | 20 |
| UNAUTHORIZED_POLICY_OVERLAP | 20 |

## Detector vs ground truth (evaluation only)

Ground-truth anomalies: **130**, detected: **130**, TP **130**, FP **0**, FN **0**, precision **100.00%**, recall **100.00%**, F1 **1.0**.

| Issue type | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| DUPLICATE_TRANSACTION | 10 | 0 | 0 | 100.00% | 100.00% |
| ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT | 20 | 0 | 0 | 100.00% | 100.00% |
| INVALID_DATE_SEQUENCE | 10 | 0 | 0 | 100.00% | 100.00% |
| INVALID_FOREIGN_KEY | 10 | 0 | 0 | 100.00% | 100.00% |
| POLICY_WITHOUT_ACCEPTANCE | 20 | 0 | 0 | 100.00% | 100.00% |
| PREMIUM_FORMULA_MISMATCH | 20 | 0 | 0 | 100.00% | 100.00% |
| RENEWAL_FOR_CANCELLED_POLICY | 20 | 0 | 0 | 100.00% | 100.00% |
| UNAUTHORIZED_POLICY_OVERLAP | 20 | 0 | 0 | 100.00% | 100.00% |

### Edge-case labels (expected behaviours, not defects)

| Label | Count |
|---|---|
| CANCELLED_POLICY | 142 |
| DECLINED_RENEWAL | 354 |
| HIGH_RISK_REFERRAL | 205 |
| MID_TERM_ASSET_CHANGE | 59 |
| MISSING_RISK_INFORMATION | 624 |

## Honest limitations of this evaluation

- Perfect precision/recall reflects that anomalies are injected through well-defined, rule-detectable mutations; it does **not** imply the detector would catch arbitrary real-world data defects.
- The clean baseline (anomaly injection off) yields **0 findings** - verified by `test_clean_baseline_has_zero_findings_and_perfect_reconciliation` on the starter scale.
- Generator notes: none.
