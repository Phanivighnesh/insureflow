# API Contract (generated from the implemented FastAPI routes - do not edit by hand)

Regenerate: `cd backend && python -m scripts.generate_api_contract --write`. A pytest (`test_api_contract_in_sync`) fails if this file or `docs/openapi.json` is stale. Interactive docs: `/docs` (Swagger) when the server runs.

**Conventions.** Base path `/api`. JSON bodies; unknown request fields are rejected (422). Errors always use
`{"error": {"code": "...", "message": "...", "details": []}}` with 401 (no/invalid/expired token), 403 (role/authority), 404 (missing **or not yours** for customers), 409 (state conflict, e.g. issuance prerequisites), 422 (validation).
Lists accept `page`, `page_size` (max 200) and return `{items, total, page, page_size}`.

**Authentication (DEMO ENVIRONMENT ONLY - not production auth).** `POST /api/auth/demo-session` returns an HMAC-signed bearer token (default TTL 12h; set `SESSION_SECRET` in any shared deployment).
Customers get an isolated `customer_key`; staff roles (`OPERATIONS_ANALYST`, `RISK_REVIEWER`, `ADMINISTRATOR`) require `access_code` = `STAFF_ACCESS_CODE`. Send `Authorization: Bearer <token>`.
Customers can only reach records of applicants they created; other customers' IDs return 404. Underwriting approvals are additionally gated by **approval authority** (analyst < risk reviewer < administrator/senior).

**Business logic lives in `app/services/workflow.py`; routes only authenticate, authorise, validate shape, call the service and serialise.**

| Role string in the table | Meaning |
|---|---|
| `public` | no token required |
| `any authenticated` | any valid session |
| `CUSTOMER` | customer sessions only |
| `STAFF` | OPERATIONS_ANALYST, RISK_REVIEWER or ADMINISTRATOR |


## operations

| Method | Path | Access | Handler / summary |
|---|---|---|---|
| POST | `/api/ai/chat` | STAFF | `chat`  |
| POST | `/api/ai/explain-decision` | STAFF | `explain_decision`  |
| POST | `/api/ai/explain-exception` | STAFF | `explain_exception`  |
| GET | `/api/ai/status` | STAFF | `ai_status`  |
| GET | `/api/applicants` | STAFF | `list_applicants`  |
| GET | `/api/applicants/{applicant_id}` | STAFF | `get_applicant`  |
| GET | `/api/assets` | STAFF | `list_assets`  |
| GET | `/api/assets/{asset_id}` | STAFF | `get_asset`  |
| GET | `/api/audit` | STAFF | `audit_log`  |

## auth

| Method | Path | Access | Handler / summary |
|---|---|---|---|
| POST | `/api/auth/demo-session` | public | `demo_session` - DEMO ONLY. Customers receive an isolated session; staff roles need the staff access code. |
| GET | `/api/auth/me` | any authenticated | `me`  |

## customer

| Method | Path | Access | Handler / summary |
|---|---|---|---|
| GET | `/api/customer/demo-scenarios` | public | `demo_scenarios` - Prefilled INPUTS only. Submit one to POST /customer/quotes; the backend produces the outcome. |
| POST | `/api/customer/payments/{payment_id}/resolve` | CUSTOMER | `resolve`  |
| GET | `/api/customer/policies` | CUSTOMER | `list_policies`  |
| GET | `/api/customer/policies/{policy_id}` | CUSTOMER | `get_policy`  |
| POST | `/api/customer/policies/{policy_id}/cancel` | CUSTOMER | `cancel`  |
| POST | `/api/customer/policies/{policy_id}/endorsements` | CUSTOMER | `endorse`  |
| POST | `/api/customer/policies/{policy_id}/renewals` | CUSTOMER | `request_renewal`  |
| GET | `/api/customer/products` | public | `products`  |
| GET | `/api/customer/quotes` | CUSTOMER | `list_quotes`  |
| POST | `/api/customer/quotes` | CUSTOMER | `submit_quote`  |
| GET | `/api/customer/quotes/{quote_id}` | CUSTOMER | `get_quote`  |
| POST | `/api/customer/quotes/{quote_id}/accept` | CUSTOMER | `accept`  |
| POST | `/api/customer/quotes/{quote_id}/information` | CUSTOMER | `provide_info`  |
| POST | `/api/customer/quotes/{quote_id}/payment` | CUSTOMER | `pay` - DEMO PAYMENT - no real payment processing. |
| GET | `/api/customer/renewals` | CUSTOMER | `list_renewals`  |
| POST | `/api/customer/renewals/{renewal_id}/accept` | CUSTOMER | `accept_renewal`  |
| POST | `/api/customer/renewals/{renewal_id}/decline` | CUSTOMER | `decline_renewal`  |

## operations

| Method | Path | Access | Handler / summary |
|---|---|---|---|
| GET | `/api/dashboard/exceptions` | STAFF | `dashboard_exceptions`  |
| GET | `/api/dashboard/renewals` | STAFF | `dashboard_renewals`  |
| GET | `/api/dashboard/summary` | STAFF | `dashboard_summary`  |
| GET | `/api/dashboard/underwriting` | STAFF | `dashboard_underwriting`  |

## data/validation

| Method | Path | Access | Handler / summary |
|---|---|---|---|
| GET | `/api/data/export` | RISK_REVIEWER, ADMINISTRATOR | `export_list`  |
| GET | `/api/data/export/{kind}/{name}` | RISK_REVIEWER, ADMINISTRATOR | `export_download`  |
| POST | `/api/data/generate` | ADMINISTRATOR | `generate` - DESTRUCTIVE: replaces ALL dataset records (customer submissions included). Requires confirm=true. |
| GET | `/api/data/reproducibility` | STAFF | `repro_report`  |
| POST | `/api/data/reproducibility-check` | ADMINISTRATOR | `repro` - Regenerates twice in isolated in-memory databases (never touches live data) and compares checksums. |
| GET | `/api/data/status` | STAFF | `status`  |
| GET | `/api/data/validation` | STAFF | `latest_validation`  |

## operations

| Method | Path | Access | Handler / summary |
|---|---|---|---|
| GET | `/api/endorsements` | STAFF | `list_endorsements`  |
| POST | `/api/endorsements` | STAFF | `create_endorsement`  |
| POST | `/api/endorsements/{endorsement_id}/approve` | STAFF | `approve_endorsement`  |
| POST | `/api/endorsements/{endorsement_id}/reject` | STAFF | `reject_endorsement`  |
| GET | `/api/exceptions` | STAFF | `list_exceptions`  |
| GET | `/api/exceptions/{exception_id}` | STAFF | `get_exception`  |
| POST | `/api/exceptions/{exception_id}/resolution` | STAFF | `resolve_exception`  |

## health

| Method | Path | Access | Handler / summary |
|---|---|---|---|
| GET | `/api/health` | public | `health`  |

## operations

| Method | Path | Access | Handler / summary |
|---|---|---|---|
| GET | `/api/policies` | STAFF | `list_policies`  |
| GET | `/api/policies/{policy_id}` | STAFF | `get_policy`  |
| POST | `/api/policies/{policy_id}/cancel` | STAFF | `cancel`  |
| GET | `/api/quotes` | STAFF | `list_quotes`  |
| GET | `/api/quotes/{quote_id}` | STAFF | `get_quote`  |
| GET | `/api/quotes/{quote_id}/audit` | STAFF | `quote_audit`  |
| POST | `/api/quotes/{quote_id}/evaluate` | STAFF | `evaluate`  |
| GET | `/api/renewals` | STAFF | `list_renewals`  |
| POST | `/api/renewals/generate` | STAFF | `generate_renewal`  |
| POST | `/api/renewals/{renewal_id}/accept` | STAFF | `accept_renewal`  |
| POST | `/api/renewals/{renewal_id}/decline` | STAFF | `decline_renewal`  |
| GET | `/api/underwriting/decisions` | STAFF | `decisions`  |
| GET | `/api/underwriting/pending` | STAFF | `pending`  |
| POST | `/api/underwriting/{decision_id}/approve` | STAFF | `route`  |
| POST | `/api/underwriting/{decision_id}/reject` | STAFF | `route`  |
| POST | `/api/underwriting/{decision_id}/request-information` | STAFF | `route`  |

## data/validation

| Method | Path | Access | Handler / summary |
|---|---|---|---|
| POST | `/api/validation/run` | RISK_REVIEWER, ADMINISTRATOR | `run_validation_endpoint`  |

_64 endpoints._ Request/response schemas: see `docs/openapi.json`.
