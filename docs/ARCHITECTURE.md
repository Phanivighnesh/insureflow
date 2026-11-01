# Architecture

```
React (customer portal + ops dashboard)  --HTTP-->  FastAPI routers (thin)  -->  services/workflow.py
                                                                                    |  uses
                                                  engines/ (pure, deterministic): eligibility, risk, premium, underwriting, policy
                                                                                    |  reads
                                                  core/rules_config.py (single rules source)
                                                  models/ + database/ (SQLAlchemy -> SQLite | PostgreSQL)
AI copilot (Phase 5) --> safe query tools --> grounded context --> Groq (explain only) | deterministic template fallback
```

## Layers (implemented)
- `core/rules_config.py` - every rate, factor, weight, limit, threshold, authority (versioned `RULES-1.0.0`).
- `engines/*` - **pure functions**, no DB access, no randomness, no clock. Unit-tested in isolation.
- `services/workflow.py` - the only place state changes. Used by customer API, ops API and the generator. Takes an injectable `now`.
- `services/seed.py` - idempotent master data from config. `services/ids.py` - deterministic IDs.
- `core/security.py` - `Actor(user_id, role, customer_key)`; `assert_can_access_applicant` blocks cross-customer access.

## Workflows
**Customer → policy**
1. Select product → submit applicant + asset + coverage (`submit_application`).
2. Backend persists applicant/asset/quote, runs eligibility → risk → premium → decision, writes RiskAssessment, UnderwritingDecision and audit events.
3. APPROVED: customer `accept_quote` → `demo_payment(SUCCESS|FAILED|PENDING)` → `issue_policy` (guard re-checks all prerequisites + overlap/duplicate).
4. REFERRED: appears in the Underwriting Center for the required authority. PENDING_INFORMATION: `provide_information` re-evaluates (new decision). DECLINED: terminal with reasons.

**Operations**
`review_quote(APPROVE|REJECT|REQUEST_INFORMATION)` validates role authority and appends a MANUAL decision. Policies: `cancel_policy`, `request_endorsement` / `decide_endorsement` (authority by coverage band), `generate_renewal` / `respond_renewal`, `expire_policies`. Every action → `AuditEvent`.

**Exception path**: preventive guards raise `ConflictError` with the issue code (e.g. `UNAUTHORIZED_POLICY_OVERLAP`, `RENEWAL_FOR_CANCELLED_POLICY`, `ENDORSEMENT_EXCEEDS_PRODUCT_LIMIT`). Phase 3 injects these as labelled anomalies (separate from baseline generation) and a validation engine detects them independently of `ground_truth`.

## Error model
`DomainError` subclasses carry `status_code`, `code`, `message`, `details[]` → API maps to `{ "error": {code, message, details} }`.

## Security posture
Demo-environment only: opaque demo-session tokens with roles, no production auth. DEMO PAYMENT only - no card data. API keys server-side env only.

## API layer (Phase 2)
`app/main.py::create_app(settings, engine)` builds the app (lazy module-level `app`, so imports never touch a DB). Routers: `routes_auth` (demo sessions), `routes_customer` (own-records only; foreign IDs → 404), `routes_ops` (staff dashboards/lists/review/endorsements/renewals/exceptions/audit), `routes_data` (generation, validation, exports; admin/reviewer). `api/deps.py`: HMAC-signed bearer tokens, `require_roles`, request-scoped DB session that commits on success and rolls back on any error. `api/serializers.py`: presentation only. Every state change calls `services/workflow.py` (no business logic in routes). Authority gating (analyst < risk reviewer < senior/admin) is enforced inside the workflow, so it applies to every caller.

## Data generation & validation (Phase 3)
`app/data_generator/` (config, profiles, pipeline, anomalies, export, runner, CLI) drives `workflow` with a simulated clock. `engines/validation_engine.py` is an independent detector that reads business tables only. `services/evaluation.py` computes business metrics and - as the **only** ground-truth reader - precision/recall. See `docs/DATA_GENERATION.md`.
