# Synthetic Data Generation

**All data is synthetic.** No real customer information and no external datasets are used (nothing to license/attribute). Names come from small built-in lists; emails use `@example.test`.

## Commands
```
cd backend
python -m app.data_generator --seed 20261022 --scale starter          # ~150 applicants, fast (≈4s)
python -m app.data_generator --seed 20261022 --scale full             # 3,000 / 4,000 / 2,000 / 1,200 (≈1.5-2 min)
python -m app.data_generator --scale full --no-anomalies              # baseline only
python -m app.data_generator --scale full --repro-check               # + regenerate twice in memory and compare checksums
# options: --out DIR (default data/exports/<scale>)  --db SQLALCHEMY_URL (default sqlite file inside --out)
```
Via API (ADMINISTRATOR): `POST /api/data/generate {"seed":20261022,"scale":"full","anomalies":true,"confirm":true}` (destructive, runs in a background thread; poll `GET /api/data/status`). `POST /api/data/reproducibility-check` runs the checksum comparison in isolated in-memory databases.

## Pipeline (same code for starter and full)
1. Reset dataset tables, seed master data (Product, CoverageOption, ProductCoverage, RiskFactor, ApprovalAuthority) from `rules_config.py`.
2. **Quotes** - applicant profiles + asset attributes sampled with a seeded `random.Random(f"{seed}:{stage}")`; each quote is submitted through `workflow.submit_application` with a simulated clock, so eligibility, risk, premium, decision, IDs and audit events are produced by the real engines. ~6% of quotes omit a mandatory field, ~9% are high-hazard profiles.
3. Provide-information (55% of pending), manual referral review (by the authority level each referral requires; recent referrals stay pending), acceptance, payments (88% direct success, 8% fail-then-success, 4% pending-then-resolved), policy issuance.
4. Lifecycle: ~5% cancellations, ~12% endorsements (approved / rejected / pending / auto-rejected for limit breach; asset-change types labelled MID_TERM_ASSET_CHANGE).
5. **Renewals** generated inside the 60-day window at simulated dates; 45% accepted (creating a renewal-term policy), the rest declined / left open (then EXPIRED) / withdrawn by later cancellation.
6. Maintenance (`expire_stale_renewals`, `expire_policies` at the fixed as-of date 2026-10-22).
7. **Anomaly injection** (`anomalies.py`, switchable) - separate stage using its own RNG stream.
8. Ground truth persisted last; validation + metrics; export.

Volume accounting (the totals are the specified volumes *including* additive anomalies): policies = quote-issued + accepted renewals + overlap anomalies = 2,000; renewals = baseline + RENEWAL_FOR_CANCELLED anomalies = 1,200; quotes = baseline + overlap-anomaly quotes = 4,000. A top-up step covers any shortfall and records a note if it cannot.

## Labelled anomalies (full scale: 20 each core / 10 each extra)
| issue_type | Injection (one targeted record each) | Detector rule |
|---|---|---|
| POLICY_WITHOUT_ACCEPTANCE | acceptance record removed from a valid policy | issuance check: no acceptance for quote |
| PREMIUM_FORMULA_MISMATCH | premium (policy+quote+payment, or quote only) scaled away from the formula | independent recalculation vs recorded, tolerance 0.01 |
| ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT | APPROVED endorsement 110-150% over option max | limits check on approved endorsements |
| RENEWAL_FOR_CANCELLED_POLICY | renewal generated after cancellation | renewal generated after cancellation or live status on cancelled policy |
| UNAUTHORIZED_POLICY_OVERLAP | second, otherwise-valid policy on same asset/product, no reason | `find_unauthorized_overlaps` (permitted: `overlap_reason`, renewal chain) |
| INVALID_FOREIGN_KEY | payment → non-existent policy (SQLite only; FK enforcement lifted for this insert) | generic FK scan over model metadata |
| DUPLICATE_TRANSACTION | second SUCCESS payment for a quote | >1 successful payment per quote/renewal |
| INVALID_DATE_SEQUENCE | acceptance timestamp before quote creation | date-ordering checks |

Edge-case labels (`record_category = EDGE_CASE`, expected behaviours not defects): MISSING_RISK_INFORMATION, HIGH_RISK_REFERRAL, MID_TERM_ASSET_CHANGE, CANCELLED_POLICY, DECLINED_RENEWAL.

## Ground truth
`ground_truth/ground_truth.{csv,json}` + table `ground_truth` (issue_type, ground_truth_label, expected_outcome, affected_entity, affected_record_id, severity, record_category). It is exported to a separate directory, never joined into feature tables, and read only by `services/evaluation.py` for precision/recall.

## Determinism rules (verified by tests + full-scale check)
Seeded per-stage RNG; no wall-clock or UUID in data; IDs from counters; simulated `now` passed to every workflow call; exports sorted by primary key with fixed column order and canonical JSON; checksums over files. Excluded from checksums: `run_metadata.json`, `dataset_runs`, `validation_runs`, `detected_exceptions`.

## Output layout (`data/exports/<scale>/`)
`csv/*.csv` (all tables), `json/*.json` (tables ≤ 5,000 rows), `seed_data.sql` (INSERTs; header disables SQLite FK checks because it contains the labelled dangling-FK rows), `ground_truth/`, `manifest.json` (config, counts, checksums, notes), `validation_report.json`, `run_metadata.json` (non-deterministic), `reproducibility_report.json`, `insureflow_<scale>.db` (SQLite copy; not committed to the ZIP).
