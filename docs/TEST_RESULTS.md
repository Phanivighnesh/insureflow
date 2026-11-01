# Test Results (actually executed)
Environment: Windows, Python 3.10.11, Node 24, SQLAlchemy 2.0, FastAPI 0.115, Vite 5.4, Vitest 2.1, React 18.3. Date: 2026-11-01.

## Summary
| Command | Result |
|---|---|
| `cd backend && python -m pytest -q` | **137 passed** (94 baseline + 43 AI copilot tests, ~140 s) |
| `cd frontend && npm run typecheck` (strict) | **0 errors** |
| `cd frontend && npm run build` | **OK** (initial JS 284 kB; `Copilot-*.js` code-split 12 kB) |
| `cd frontend && npm test` | **18 passed** (4 test files, ~35 s), boots the real FastAPI server in `tests/globalSetup.ts` |
| Frontend secrets check | `grep` on `dist/` confirms `gsk_`, `GROQ`, `api.groq.com` are completely absent |
| Full-scale generation + reproducibility (Phase 3, unchanged) | 3,000 / 4,000 / 2,000 / 1,200; 130 anomalies P=R=1.0; 42/42 files identical across regenerations |
| Live Groq verification | **VERIFIED** with model `openai/gpt-oss-20b` via live Groq API completions |
| Fallback verification | **VERIFIED** with 100% offline deterministic templates |

---

## Backend Test Breakdown (137 passed)
- **Baseline Tests (94 passed)**:
  - `tests/test_engines.py`: 24 passed (eligibility, risk, premium, underwriting, common)
  - `tests/test_workflow.py`: 30 passed (complete quote to policy lifecycles, cancellations, renewals, endorsements)
  - `tests/test_generator.py`: 12 passed (reproducibility checksums, profile generation, seed parity)
  - `tests/test_api.py`: 20 passed (auth, customer quotes, payments, RBAC, alembic migration drift)
  - `tests/test_api_data.py`: 8 passed (data generation, validation run, export integrity)
- **Phase 5 AI Copilot Tests (43 passed)**:
  - `tests/test_ai_intents.py` (9 passed): Regex extraction for all 7 ID types (`QTE-*`, `POL-*`, `APP-*`, `EXC-*`, `REN-*`, `END-*`, `UWD-*`), lookbehind non-collision, priority intent classification across all 11 intents.
  - `tests/test_ai_tools.py` (5 passed): Read-only fact retrieval for decisions, premiums, lifecycle histories, exceptions, applicants, senior review queues.
  - `tests/test_ai_templates.py` (3 passed): Deterministic template rendering, identical output for identical input, missing record handling.
  - `tests/test_ai_providers.py` (5 passed): Mock transport tests for 200, 401, 404, 429 retry, timeout, malformed JSON fallback.
  - `tests/test_ai_guard.py` (5 passed): Rejection of unknown IDs, fabricated numbers, forbidden state mutation claims, confidence validation.
  - `tests/test_ai_governance.py` (3 passed): AST static analysis proving zero `GroundTruth` imports in `app/ai/**`, zero workflow mutator imports, zero DB row mutations during tool execution.
  - `tests/test_ai_ratelimit.py` (4 passed): Sliding-window rate limiter per user, burst allowance, recovery after window expiration.
  - `tests/test_ai_api.py` (9 passed): Anonymous 401, customer 403 on all `/api/ai/*` routes, staff 200, status discovery, unknown IDs returning 200 not-found, strict `extra="forbid"` 422 validation, 429 rate limit enforcement.

---

## Frontend Integration Tests (18 passed)
| File | Tests |
|---|---|
| `tests/journey.test.ts` (baseline, 5 tests) | Complete 12-step journey from submission to policy issuance, failed demo payment recovery, data generation, validation runs, policy lifecycle endorsements & renewals. |
| `tests/ui.test.tsx` (baseline, 7 tests) | Customer portal wizards, scenario prefill, ops referral reviews, data validation dashboard, route guards. |
| `tests/ai.journey.test.ts` (new, 4 tests) | AI status endpoint reporting, grounded quote referral explanation with real rule citations, unknown ID handling, 401/403/429 mapping. |
| `tests/ai.ui.test.tsx` (new, 2 tests) | Route guard redirection from `/ops/copilot` when unauthenticated; operations analyst sign-in, navigation to AI Copilot, suggested question click, structured answer rendering (Summary, Key Findings, Supporting Rules, Detailed Explanation). |

---

## Mutation Checks (deliberate break → test failure → restored)
| Mutation | Target Component | Result / Error Observed | Restored |
|---|---|---|---|
| Disabled ID check in anti-hallucination guard | `app/ai/guard.py` | `test_guard_rejects_unknown_id` failed (`assert True is False`, unknown ID allowed) | ✅ Yes |
| Removed `staff_only` dependency from `/api/ai/chat` | `app/api/routes_ai.py` | `test_ai_customer_forbidden` failed (`AttributeError: 'Session' object has no attribute 'user_id'`) | ✅ Yes |
| Imported `GroundTruth` into AI retrieval tools | `app/ai/tools.py` | `test_ast_prohibits_ground_truth_imports` failed (`AssertionError: app/ai/tools.py imports GroundTruth from app.models`) | ✅ Yes |

---

## Live Groq Integration Verification
- **Status**: **VERIFIED**
- **Model**: `openai/gpt-oss-20b`
- **Observed Behavior**:
  - Live query: *"Why was QTE-2026-004001 declined?"*
  - Provider response: `groq` (`used_fallback: false`, `latency: 480ms`).
  - Answer grounded strictly in database facts (property value $49,991 below $50,000 threshold, coverage $60,000 exceeds cap, missing `previous_claims`).
  - Output verified by anti-hallucination guard with 0 violations.
- **Offline Fallback**:
  - When `GROQ_API_KEY` is omitted or invalid, automatically falls back to deterministic template engine without error.
