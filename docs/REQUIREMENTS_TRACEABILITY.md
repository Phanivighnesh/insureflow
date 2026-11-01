# Requirements Extraction & Traceability Matrix

Sources: **PS** = original problem statement, **MP** = master engineering prompt (Parts 1-19), **PI** = project instructions.
Precedence on conflict: original acceptance criteria > Part 19 (24-hour plan) > documented engineering judgment. The 5-6 hour deadline is superseded by 24 hours.

Status key: ✅ implemented **and covered by executed tests** | 🟡 partially done | ⬜ not started (planned phase shown)

## A. Business logic & engines
| ID | Requirement | Source | Implementation | Status |
|---|---|---|---|---|
| BL-01 | 3 product lines (Motor, Property, Commercial) with documented, configurable rules in ONE central config | MP P2, P19.4 | `app/core/rules_config.py` | ✅ |
| BL-02 | Eligibility engine → ELIGIBLE / INELIGIBLE / NEEDS_INFORMATION, explainable checks | MP P6 | `engines/eligibility_engine.py` | ✅ |
| BL-03 | Weighted risk score, configurable thresholds, factors + missing info + explanation; missing ≠ 0 | MP P6 | `engines/risk_engine.py` | ✅ |
| BL-04 | Transparent premium formula, factor tables, charges, formula version, snapshot, independent recalculation, tolerance/rounding policy | MP P5 | `engines/premium_engine.py`, `Quote.premium_breakdown` | ✅ (calc timestamp = `PREMIUM_CALCULATED` audit event) |
| BL-05 | Outcomes APPROVED/REFERRED/DECLINED/PENDING_INFORMATION; every decision persisted as new record with ID, quote, risk score, reasons, rule IDs, authority, reviewer, timestamp, engine version | MP P6 | `engines/underwriting_engine.py`, `UnderwritingDecision` | ✅ |
| BL-06 | Approval authority levels (automated/analyst/risk reviewer/senior) from risk, coverage, exception rules; high risk never auto-approved | MP P6 | `underwriting_engine.py`, config | ✅ |
| BL-07 | Policy issuance only if eligible + approved + accepted + payment satisfied + no blocking exception | PS, MP P7 | `policy_engine.check_issuance_prerequisites`, `workflow.issue_policy` | ✅ |
| BL-08 | Policy lifecycle states + valid transitions | MP P7 | `policy_engine.TRANSITIONS`, `_transition` | ✅ (pre-issuance states live on Quote; see TECHNICAL_DECISIONS) |
| BL-09 | Cancellation with history | MP P7 | `workflow.cancel_policy` | ✅ |
| BL-10 | Endorsements: valid policy, snapshot, requested changes, limit validation, approval/rejection, effective date, audit, never overwrite policy | MP P7 | `workflow.request/decide_endorsement` | ✅ |
| BL-11 | Renewals: eligibility (status, expiry, cancellation, payments, risk), separate historical records, statuses, no valid renewal for cancelled policy | MP P7 | `workflow.generate_renewal/respond_renewal` | ✅ |
| BL-12 | Mid-term asset change; declined renewal; cancelled policy scenarios | PS | Endorsement types; `respond_renewal(accept=False)`; `cancel_policy` | ✅ (mid-term asset change available via endorsement; data-volume coverage pending in generator) |

## B. Data model
| ID | Requirement | Source | Implementation | Status |
|---|---|---|---|---|
| DB-01 | 10 core entities + supporting tables (ProductCoverage, QuoteCoverage, PolicyCoverage, RiskAssessment, Payment, AuditEvent, PolicyStatusHistory, GroundTruth, ApprovalAuthority) | MP P3 | `models/entities.py` (21 tables) | ✅ |
| DB-02 | PKs, FKs, enums, CHECK/unique constraints, indexes; FK enforced in SQLite | MP P3 | models + `database/session.py` | ✅ (`test_foreign_keys_enforced`) |
| DB-03 | Deterministic zero-padded IDs (APP/AST/QTE/POL/END/REN, PROD, COV, RSK) | PS, MP P3 | `services/ids.py` | ✅ |
| DB-04 | Cardinalities incl. Quote→Policy 1:0..1, bridge tables for N:M | MP P3 | models | ✅ |
| DB-05 | Append-only history (decisions, status history, endorsements, renewals, audit) | PS, PI | workflow | ✅ |
| DB-06 | Alembic migrations; PostgreSQL + SQLite | P19.7 | `migrations/` (0001 baseline, 0002 run metadata); `test_alembic_upgrade_matches_models` (upgrade→no model drift→downgrade on SQLite); `test_ddl_compiles_for_postgresql` | ✅ SQLite / 🟡 PostgreSQL DDL compiles, **never run against a live Postgres server** |
| DB-07 | Full data dictionary (type, required, allowed, units, uniqueness, validation) | PS step 1 | `docs/DATA_DICTIONARY.md` generated from models by `scripts/generate_data_dictionary.py` | ✅ |

## C. Synthetic data, anomalies, validation
| ID | Requirement | Source | Plan | Status |
|---|---|---|---|---|
| GEN-01 | Generator CLI `python -m app.data_generator --seed 20261022 --scale starter|full`, same code for both | PS, MP P4 | `app/data_generator/` (`GenConfig`, `runner.py`, `__main__.py`) | ✅ |
| GEN-02 | Volumes: 3,000 applicants / 4,000 quotes / 2,000 policies / 1,200 renewals; 3 products | PS | **Verified by an actual full run**: exactly 3,000 / 4,000 / 2,000 / 1,200 (`docs/VALIDATION_REPORT.md`); starter scale asserted in tests | ✅ |
| GEN-03 | Dependency order; derived values computed from sources (reuses `workflow` + engines with injected clock) | PS, MP P4 | `pipeline.py` drives `services/workflow.py`; `test_derived_values_are_consistent_with_sources` | ✅ |
| GEN-04 | Reproducibility: same seed ⇒ identical checksums; run metadata separate | MP P4, P19.6 | `runner.reproducibility_check`, `export.py`; `docs/REPRODUCIBILITY_REPORT.md` (full scale: identical, 42 files); mutation-tested | ✅ |
| EXC-01..05 | Inject labelled anomalies: POLICY_WITHOUT_ACCEPTANCE, PREMIUM_FORMULA_MISMATCH, ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT, RENEWAL_FOR_CANCELLED_POLICY, UNAUTHORIZED_POLICY_OVERLAP | PS, MP P8 | `data_generator/anomalies.py` (separate stage, `--no-anomalies` switch, 20 each at full scale); prevention also tested in workflow | ✅ |
| EXC-06 | Extras: missing risk info, high-risk referral, invalid FK, duplicate transactions, invalid dates | MP P8 | INVALID_FOREIGN_KEY, DUPLICATE_TRANSACTION, INVALID_DATE_SEQUENCE injected (10 each, full); edge cases MISSING_RISK_INFORMATION, HIGH_RISK_REFERRAL, MID_TERM_ASSET_CHANGE, CANCELLED_POLICY, DECLINED_RENEWAL labelled. FK injection is SQLite-only (needs FK enforcement off) | ✅ (SQLite) |
| GT-01 | `ground_truth` table/CSV/JSON (issue_type, ground_truth_label, expected_outcome, affected_entity, affected_record_id); never an input to engines/detector | PS, MP P9 | exported to separate `ground_truth/` dir; only `services/evaluation.py` reads it; AST test proves the detector never references it | ✅ |
| VAL-01 | Validation engine: PK, FK, duplicates, enums, dates, lifecycle, premium recon, limits, issuance, renewal, overlaps, mandatory, CSV↔DB consistency; structured report | MP P9 | `engines/validation_engine.py` (13 check groups; PK uniqueness is DB-enforced). CSV↔DB parent-reference consistency tested (`test_csv_exports_reference_existing_parents`) | ✅ (no standalone CSV-vs-DB checker endpoint) |
| MET-01 | Metrics incl. precision/recall/FP/FN vs ground truth; no hardcoded stats | MP P9 | `services/evaluation.py`; persisted in `validation_runs`; served by `/api/data/validation` | ✅ |
| EXP-01 | CSV/JSON/SQL exports, README, dictionary, manifest, validation summary, reproducibility report | PS step 9 | `data/exports/full/` (csv/, json/, seed_data.sql, manifest.json, validation_report.json, ground_truth/) + docs | ✅ (JSON omitted for tables > 5,000 rows) |

## D. Customer portal & operations
| ID | Requirement | Source | Plan | Status |
|---|---|---|---|---|
| CP-01 | Customer API: products, quote submit, accept, demo payment, policies, renewal accept/decline | P19.5 | `api/routes_customer.py`; `test_full_customer_to_policy_workflow_visible_to_operations` | ✅ |
| CP-02 | Customer pages (landing, product, dynamic form, coverage, result, accept, DEMO PAYMENT, dashboard) | MP addl module | `frontend/src/pages/customer/*`; UI test drives login → scenario → wizard → result → accept → FAILED then SUCCESS demo payment → policy against the live backend | ✅ |
| CP-03 | Demo scenarios (5) executed by real backend | MP addl module | `ScenarioPanel` loads prefilled INPUTS from `GET /customer/demo-scenarios`; outcomes come from the engines (client + UI tests) | ✅ |
| CO-01 | Same DB, services, engines for customer & ops; customer submissions immediately visible to ops | MP addl module | single `workflow` service; UI test: separate ops session finds the customer's exact quote, premium and policy | ✅ |
| RB-01 | RBAC: Customer, Analyst, Risk reviewer, Admin; demo-session isolation; no cross-customer access | P19.3 | `api/deps.py` (signed tokens, `require_roles`), authority gating in workflow. Tests: 401 for missing/forged/expired tokens, 403 role matrix, cross-customer 404 on 8 endpoints, authority levels over HTTP; **mutation-tested**. DEMO auth only (no passwords/MFA/revocation) | ✅ for demo environment / ⛔ not production auth |
| OPS-01 | 11 internal pages (overview, applicants, assets, quotes, underwriting center, policies, endorsements, renewals, exceptions/audit, copilot, data gen) | MP P11 | All 11 built under `frontend/src/pages/ops/*` (overview, applicants, assets, quotes, underwriting, policies, endorsements, renewals, exceptions + audit log, data & validation, and AI copilot at `/ops/copilot`). | ✅ |
| API-01 | REST + OpenAPI, pagination/filtering, error model, CORS | MP P12 | 60 endpoints; `docs/API_CONTRACT.md` + `docs/openapi.json` generated from routes and sync-tested; uniform error envelope | ✅ (CORS configured via `CORS_ORIGINS`, see tests) |

## E. AI, quality, delivery
| ID | Requirement | Source | Plan | Status |
|---|---|---|---|---|
| AI-01 | Groq copilot (explain decisions, premiums, anomalies, NL questions) over safe backend tools; LLM never decides; deterministic fallback; key server-side | MP P10 | `backend/app/ai/*` + `api/routes_ai.py`. Safe tools, regex entity classifier, prompt v1.0.0, Groq provider (`openai/gpt-oss-20b`) + offline template fallback, anti-hallucination guard, read-only session, AST static check, sliding-window rate limiter. Verified live with Groq and verified in fallback. | ✅ |
| TST-01 | Pytest coverage for the 16 listed areas | MP P14 | All 16 areas covered (see `docs/TEST_RESULTS.md`) | ✅ |
| DOC-01 | AGENTS.md ×3, handoff docs, README, .env.example | PI | this phase | ✅ |
| DOC-02 | Validation/reproducibility reports, source manifest, no-real-data statement | MP P15 | `docs/VALIDATION_REPORT.md`, `docs/REPRODUCIBILITY_REPORT.md` (rendered from real run artifacts), `manifest.json` | ✅ |
| DEP-01 | Vercel + Render + Neon/Supabase config and verified URLs | MP P1 | `frontend/vercel.json`, `backend/Dockerfile`, `render.yaml` written; **never deployed — no URL verified** | 🟡 config only |

## F. Frontend & integration (Phase 4)
| ID | Requirement | Evidence | Status |
|---|---|---|---|
| FE-01 | React + Vite + TS + Tailwind + Router + TanStack Query + Lucide + Recharts | `frontend/package.json`; `tsc --noEmit` strict clean; production build OK | ✅ |
| FE-02 | Customer: demo access, product selection, application wizard (product-specific fields), coverage selection, submission | `Public.tsx`, `Apply.tsx` (fields rendered from `GET /customer/products`) | ✅ |
| FE-03 | Quote result: eligibility, underwriting outcome, premium breakdown only for actionable offers | `Quote.tsx`; UI test: DECLINED shows reasons and **no premium card/accept button** | ✅ |
| FE-04 | Accept, clearly labelled DEMO PAYMENT, failed payment issues nothing, success issues policy | UI + client tests | ✅ |
| FE-05 | Customer dashboard, applications, policies, policy detail, renewals & endorsement info | `Account.tsx`, `PolicyView.tsx`; endorsement UI test (valid → Pending, over-limit → auto-rejected with code) | ✅ (renewal UI covered via client test + backend tests; no dedicated UI-render test) |
| FE-06 | Ops: login, overview with real metrics/charts, applicants, assets, quotes, underwriting queue + review actions with confirmation, policies, endorsements, renewals, exceptions, audit, data & validation | `pages/ops/*`; UI tests for login, same-record visibility, referral approval, endorsement approval, role-gated data page | ✅ (Data generation button exercised only up to the confirmation dialog in UI tests; generation itself tested via client/API) |
| FE-07 | Centralised API client, token attach, 401/403/404/422 handling, session persistence, role-protected routes | `api/client.ts`, `auth/AuthContext.tsx`; mutation-tested (removing the token fails 12/12; relaxing the guard fails its test) | ✅ |
| FE-08 | Loading, error and empty states; pagination, search, filters; confirmation dialogs; toasts | `components/ui.tsx` and pages | ✅ (not visually reviewed in a real browser) |
| FE-09 | The 12-step customer→ops→policy journey on the real stack | `tests/journey.test.ts` (client) + `tests/ui.test.tsx` (React UI), 12 tests, stable over repeated runs | ✅ |
| FE-10 | Minimal backend corrections only where integration required | (1) `TransactionalRoute`: commit **before** response (read-after-write race found by live tests; regression test mutation-verified); (2) `provide_information` derives `year_built` for property (test added). No engines/models/routes rewritten | ✅ |
| FE-11 | AI copilot UI | `frontend/src/pages/ops/Copilot.tsx` lazy route `/ops/copilot`, conversation history in state + `sessionStorage`, suggested questions, provider status badge, structured response sections, record reference links, contextual 'Ask Copilot' buttons on Quotes, Policies, Exceptions. Tested in `tests/ai.ui.test.tsx` and `tests/ai.journey.test.ts`. | ✅ |
