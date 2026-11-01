# DATA DICTIONARY (generated from `backend/app/models/entities.py`)

Regenerate: `cd backend && python -m scripts.generate_data_dictionary > ../docs/DATA_DICTIONARY.md`

Units: monetary columns are `USD` with 2 decimals; dates ISO-8601; timestamps naive UTC. `Allowed values` come from DB CHECK constraints; deeper validation rules are in `docs/BUSINESS_RULES.md`.


## `ai_interactions`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| interaction_id | VARCHAR(24) | yes | PK |  |  |
| user_id | VARCHAR(48) | yes |  |  |  |
| role | VARCHAR(24) | yes |  |  |  |
| question | VARCHAR(500) | yes |  |  |  |
| intent | VARCHAR(40) | yes |  |  |  |
| record_refs | JSON | no |  |  |  |
| provider | VARCHAR(24) | yes |  |  |  |
| model | VARCHAR(80) | no |  |  |  |
| used_fallback | BOOLEAN | yes |  |  |  |
| fallback_reason | VARCHAR(120) | no |  |  |  |
| guard_result | JSON | no |  |  |  |
| latency_ms | INTEGER | no |  |  |  |
| prompt_version | VARCHAR(24) | no |  |  |  |
| created_at | DATETIME | yes |  |  |  |

## `applicants`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| applicant_id | VARCHAR(24) | yes | PK |  | APP-2026-000001 |
| owner_key | VARCHAR(64) | no |  |  |  |
| full_name | VARCHAR(120) | yes |  |  |  |
| email | VARCHAR(160) | no |  |  |  |
| phone | VARCHAR(32) | no |  |  |  |
| age | INTEGER | no |  |  |  |
| applicant_type | VARCHAR(16) | yes |  | INDIVIDUAL, BUSINESS |  |
| location | VARCHAR(64) | no |  |  |  |
| status | VARCHAR(12) | yes |  | ACTIVE, INACTIVE |  |
| created_at | DATETIME | yes |  |  |  |

## `audit_events`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| audit_id | VARCHAR(24) | yes | PK |  | AUD-2026-000001 |
| entity_type | VARCHAR(24) | yes |  |  |  |
| entity_id | VARCHAR(48) | yes |  |  |  |
| event_type | VARCHAR(40) | yes |  |  |  |
| actor | VARCHAR(48) | yes |  |  |  |
| actor_role | VARCHAR(24) | yes |  |  |  |
| payload | JSON | no |  |  |  |
| occurred_at | DATETIME | yes |  |  |  |

## `coverage_options`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| coverage_id | VARCHAR(16) | yes | PK |  | COV-001 |
| code | VARCHAR(40) | yes | UNIQUE |  |  |
| name | VARCHAR(80) | yes |  |  |  |
| min_limit | NUMERIC(14, 2) | yes |  |  |  |
| max_limit | NUMERIC(14, 2) | yes |  |  |  |
| rate_multiplier | NUMERIC(6, 3) | yes |  |  |  |

- Table rule: `max_limit >= min_limit`

## `dataset_runs`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| run_id | VARCHAR(16) | yes | PK |  | GEN-001 |
| seed | INTEGER | yes |  |  |  |
| scale | VARCHAR(12) | yes |  |  |  |
| anomaly_injection | BOOLEAN | yes |  |  |  |
| config | JSON | yes |  |  |  |
| status | VARCHAR(12) | yes |  |  |  |
| row_counts | JSON | no |  |  |  |
| checksums | JSON | no |  |  |  |
| reproducibility | JSON | no |  |  |  |
| notes | JSON | no |  |  |  |
| error | TEXT | no |  |  |  |
| generator_version | VARCHAR(16) | yes |  |  |  |
| started_at | DATETIME | yes |  |  |  |
| finished_at | DATETIME | no |  |  |  |
| triggered_by | VARCHAR(48) | yes |  |  |  |

## `ground_truth`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| gt_id | VARCHAR(24) | yes | PK |  | GT-000001 |
| issue_type | VARCHAR(48) | yes |  |  |  |
| ground_truth_label | VARCHAR(48) | yes |  |  |  |
| expected_outcome | TEXT | yes |  |  |  |
| affected_entity | VARCHAR(24) | yes |  |  |  |
| affected_record_id | VARCHAR(48) | yes |  |  |  |
| severity | VARCHAR(10) | yes |  |  |  |
| record_category | VARCHAR(12) | yes |  |  |  |

## `id_counters`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| key | VARCHAR(64) | yes | PK |  |  |
| value | INTEGER | yes |  |  |  |

## `products`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| product_id | VARCHAR(16) | yes | PK |  | PROD-001 |
| product_key | VARCHAR(16) | yes | UNIQUE | MOTOR, PROPERTY, COMMERCIAL |  |
| name | VARCHAR(80) | yes |  |  |  |
| base_rate | NUMERIC(10, 6) | yes |  |  |  |
| min_insured_value | NUMERIC(14, 2) | yes |  |  |  |
| max_insured_value | NUMERIC(14, 2) | yes |  |  |  |
| status | VARCHAR(12) | yes |  |  |  |
| effective_from | DATE | yes |  |  |  |
| effective_to | DATE | no |  |  |  |
| rules_version | VARCHAR(24) | yes |  |  |  |

- Table rule: `max_insured_value >= min_insured_value`

## `validation_runs`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| run_id | VARCHAR(16) | yes | PK |  | VAL-001 |
| triggered_by | VARCHAR(48) | yes |  |  |  |
| started_at | DATETIME | yes |  |  |  |
| finished_at | DATETIME | yes |  |  |  |
| checks | JSON | yes |  |  |  |
| metrics | JSON | yes |  |  |  |
| evaluation | JSON | no |  |  |  |
| finding_count | INTEGER | yes |  |  |  |

## `approval_authorities`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| authority_id | VARCHAR(24) | yes | PK |  |  |
| product_id | VARCHAR(16) | yes | FK -> products.product_id |  |  |
| level | VARCHAR(24) | yes |  |  |  |
| role | VARCHAR(24) | no |  |  |  |
| max_coverage | NUMERIC(14, 2) | no |  |  |  |
| max_risk_category | VARCHAR(8) | yes |  |  |  |

## `detected_exceptions`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| exception_id | VARCHAR(24) | yes | PK |  | EXC-VAL-001-00001 |
| run_id | VARCHAR(16) | yes | FK -> validation_runs.run_id |  |  |
| issue_type | VARCHAR(48) | yes |  |  |  |
| affected_entity | VARCHAR(24) | yes |  |  |  |
| affected_record_id | VARCHAR(48) | yes |  |  |  |
| severity | VARCHAR(10) | yes |  |  |  |
| record_date | DATE | no |  |  |  |
| detected_at | DATETIME | yes |  |  |  |
| expected_outcome | TEXT | yes |  |  |  |
| actual_outcome | TEXT | yes |  |  |  |
| details | JSON | no |  |  |  |
| resolution_status | VARCHAR(14) | yes |  |  |  |
| resolution_note | TEXT | no |  |  |  |
| resolved_by | VARCHAR(48) | no |  |  |  |

## `insured_assets`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| asset_id | VARCHAR(24) | yes | PK |  | AST-2026-000001 |
| applicant_id | VARCHAR(24) | yes | FK -> applicants.applicant_id |  |  |
| asset_type | VARCHAR(24) | yes |  | VEHICLE, PROPERTY, COMMERCIAL_ASSET |  |
| declared_value | NUMERIC(14, 2) | no |  |  |  |
| location | VARCHAR(64) | no |  |  |  |
| attributes | JSON | yes |  |  |  |
| status | VARCHAR(12) | yes |  |  |  |
| created_at | DATETIME | yes |  |  |  |

## `product_coverages`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| product_id | VARCHAR(16) | yes | PK, FK -> products.product_id |  |  |
| coverage_id | VARCHAR(16) | yes | PK, FK -> coverage_options.coverage_id |  |  |
| effective_from | DATE | yes |  |  |  |

## `risk_factors`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| risk_factor_id | VARCHAR(16) | yes | PK |  | RSK-001 |
| product_id | VARCHAR(16) | yes | FK -> products.product_id |  |  |
| code | VARCHAR(40) | yes |  |  |  |
| label | VARCHAR(80) | yes |  |  |  |
| input_field | VARCHAR(40) | yes |  |  |  |
| weight | FLOAT | yes |  |  |  |
| mandatory | BOOLEAN | yes |  |  |  |

- Table rule: `weight > 0 AND weight <= 1`

## `quotes`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| quote_id | VARCHAR(24) | yes | PK |  | QTE-2026-000001 |
| applicant_id | VARCHAR(24) | yes | FK -> applicants.applicant_id |  |  |
| asset_id | VARCHAR(24) | yes | FK -> insured_assets.asset_id |  |  |
| product_id | VARCHAR(16) | yes | FK -> products.product_id |  |  |
| coverage_id | VARCHAR(16) | no | FK -> coverage_options.coverage_id |  |  |
| coverage_code | VARCHAR(40) | no |  |  |  |
| requested_coverage | NUMERIC(14, 2) | no |  |  |  |
| status | VARCHAR(24) | yes |  | APPROVED, REFERRED, DECLINED, PENDING_INFORMATION, ACCEPTED, POLICY_ISSUED, EXPIRED |  |
| eligibility_status | VARCHAR(20) | no |  |  |  |
| eligibility_detail | JSON | no |  |  |  |
| risk_score | FLOAT | no |  |  |  |
| risk_category | VARCHAR(8) | no |  |  |  |
| premium | NUMERIC(14, 2) | no |  |  |  |
| premium_breakdown | JSON | no |  |  |  |
| input_snapshot | JSON | yes |  |  |  |
| rules_version | VARCHAR(24) | yes |  |  |  |
| valid_until | DATE | yes |  |  |  |
| created_at | DATETIME | yes |  |  |  |

## `policies`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| policy_id | VARCHAR(24) | yes | PK |  | POL-2026-000001 |
| quote_id | VARCHAR(24) | no | FK -> quotes.quote_id, UNIQUE |  |  |
| applicant_id | VARCHAR(24) | yes | FK -> applicants.applicant_id |  |  |
| asset_id | VARCHAR(24) | yes | FK -> insured_assets.asset_id |  |  |
| product_id | VARCHAR(16) | yes | FK -> products.product_id |  |  |
| coverage_id | VARCHAR(16) | yes | FK -> coverage_options.coverage_id |  |  |
| coverage_amount | NUMERIC(14, 2) | yes |  |  |  |
| premium | NUMERIC(14, 2) | yes |  |  |  |
| status | VARCHAR(24) | yes |  | DRAFT, PENDING_ACCEPTANCE, PENDING_PAYMENT, ACTIVE, CANCELLED, EXPIRED, RENEWED |  |
| start_date | DATE | yes |  |  |  |
| expiry_date | DATE | yes |  |  |  |
| cancelled_at | DATE | no |  |  |  |
| cancellation_reason | TEXT | no |  |  |  |
| overlap_reason | VARCHAR(80) | no |  |  |  |
| renewal_of_policy_id | VARCHAR(24) | no | FK -> policies.policy_id |  |  |
| snapshot | JSON | yes |  |  |  |
| issued_at | DATETIME | yes |  |  |  |

- Table rule: `expiry_date > start_date`

## `quote_acceptances`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| acceptance_id | VARCHAR(24) | yes | PK |  | ACC-2026-000001 |
| quote_id | VARCHAR(24) | yes | FK -> quotes.quote_id, UNIQUE |  |  |
| accepted_by | VARCHAR(48) | yes |  |  |  |
| accepted_at | DATETIME | yes |  |  |  |
| terms_version | VARCHAR(24) | yes |  |  |  |

## `quote_coverages`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| quote_id | VARCHAR(24) | yes | PK, FK -> quotes.quote_id |  |  |
| coverage_id | VARCHAR(16) | yes | PK, FK -> coverage_options.coverage_id |  |  |
| requested_amount | NUMERIC(14, 2) | yes |  |  |  |

## `risk_assessments`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| assessment_id | VARCHAR(24) | yes | PK |  | RAS-2026-000001 |
| quote_id | VARCHAR(24) | yes | FK -> quotes.quote_id |  |  |
| score | FLOAT | yes |  |  |  |
| category | VARCHAR(8) | yes |  | LOW, MEDIUM, HIGH |  |
| factors | JSON | yes |  |  |  |
| missing_info | JSON | yes |  |  |  |
| explanation | TEXT | yes |  |  |  |
| rules_version | VARCHAR(24) | yes |  |  |  |
| assessed_at | DATETIME | yes |  |  |  |

## `underwriting_decisions`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| decision_id | VARCHAR(24) | yes | PK |  | UWD-2026-000001 |
| quote_id | VARCHAR(24) | yes | FK -> quotes.quote_id, UNIQUE |  |  |
| sequence | INTEGER | yes | UNIQUE |  |  |
| outcome | VARCHAR(24) | yes |  | APPROVED, REFERRED, DECLINED, PENDING_INFORMATION |  |
| decision_type | VARCHAR(12) | yes |  |  |  |
| risk_score | FLOAT | no |  |  |  |
| reasons | JSON | yes |  |  |  |
| rule_ids | JSON | yes |  |  |  |
| approval_authority | VARCHAR(24) | yes |  |  |  |
| decided_by | VARCHAR(48) | yes |  |  |  |
| decided_role | VARCHAR(24) | yes |  |  |  |
| notes | TEXT | no |  |  |  |
| decided_at | DATETIME | yes |  |  |  |
| rule_engine_version | VARCHAR(24) | yes |  |  |  |

## `endorsements`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| endorsement_id | VARCHAR(40) | yes | PK |  | END-<policy-id>-001 |
| policy_id | VARCHAR(24) | yes | FK -> policies.policy_id |  |  |
| endorsement_type | VARCHAR(24) | yes |  | ASSET_MODIFICATION, COVERAGE_ADJUSTMENT, INSURED_INFO_CHANGE, DECLARED_VALUE_CHANGE |  |
| requested_changes | JSON | yes |  |  |  |
| coverage_before | NUMERIC(14, 2) | yes |  |  |  |
| coverage_after | NUMERIC(14, 2) | yes |  |  |  |
| declared_value_before | NUMERIC(14, 2) | yes |  |  |  |
| declared_value_after | NUMERIC(14, 2) | yes |  |  |  |
| premium_before | NUMERIC(14, 2) | yes |  |  |  |
| premium_after | NUMERIC(14, 2) | no |  |  |  |
| status | VARCHAR(12) | yes |  | PENDING, APPROVED, REJECTED |  |
| effective_date | DATE | yes |  |  |  |
| policy_snapshot | JSON | yes |  |  |  |
| requested_by | VARCHAR(48) | yes |  |  |  |
| requested_at | DATETIME | yes |  |  |  |
| decided_by | VARCHAR(48) | no |  |  |  |
| decided_at | DATETIME | no |  |  |  |
| decision_reason | TEXT | no |  |  |  |

## `payments`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| payment_id | VARCHAR(24) | yes | PK |  | PAY-2026-000001 |
| quote_id | VARCHAR(24) | no | FK -> quotes.quote_id |  |  |
| policy_id | VARCHAR(24) | no | FK -> policies.policy_id |  |  |
| renewal_id | VARCHAR(48) | no |  |  |  |
| amount | NUMERIC(14, 2) | yes |  |  |  |
| status | VARCHAR(10) | yes |  | SUCCESS, FAILED, PENDING |  |
| method | VARCHAR(12) | yes |  |  |  |
| is_demo | BOOLEAN | yes |  |  |  |
| idempotency_key | VARCHAR(64) | no | UNIQUE |  |  |
| created_at | DATETIME | yes |  |  |  |

- Table rule: `amount >= 0`

## `policy_coverages`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| policy_id | VARCHAR(24) | yes | PK, FK -> policies.policy_id |  |  |
| coverage_id | VARCHAR(16) | yes | PK, FK -> coverage_options.coverage_id |  |  |
| limit_amount | NUMERIC(14, 2) | yes |  |  |  |

## `policy_status_history`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| history_id | INTEGER | yes | PK |  |  |
| policy_id | VARCHAR(24) | yes | FK -> policies.policy_id |  |  |
| from_status | VARCHAR(24) | no |  |  |  |
| to_status | VARCHAR(24) | yes |  |  |  |
| changed_at | DATETIME | yes |  |  |  |
| changed_by | VARCHAR(48) | yes |  |  |  |
| reason | TEXT | no |  |  |  |

## `renewals`

| Column | Type | Required | Key | Allowed values / validation | Format / notes |
|---|---|---|---|---|---|
| renewal_id | VARCHAR(48) | yes | PK |  | REN-<policy-id>-2027 |
| policy_id | VARCHAR(24) | yes | FK -> policies.policy_id, UNIQUE |  |  |
| renewal_year | INTEGER | yes | UNIQUE |  |  |
| new_start_date | DATE | yes |  |  |  |
| new_expiry_date | DATE | yes |  |  |  |
| coverage_amount | NUMERIC(14, 2) | yes |  |  |  |
| offered_premium | NUMERIC(14, 2) | no |  |  |  |
| premium_breakdown | JSON | no |  |  |  |
| risk_score | FLOAT | no |  |  |  |
| eligibility_status | VARCHAR(20) | yes |  |  |  |
| reasons | JSON | yes |  |  |  |
| status | VARCHAR(12) | yes |  | GENERATED, OFFERED, ACCEPTED, DECLINED, EXPIRED, CANCELLED |  |
| new_policy_id | VARCHAR(24) | no | FK -> policies.policy_id |  |  |
| generated_at | DATETIME | yes |  |  |  |
| responded_at | DATETIME | no |  |  |  |
| response_reason | TEXT | no |  |  |  |
