# PROJECT STATUS  (last updated 2026-11-01 — end of Phase 5, v2)

| Phase | Scope | State |
|---|---|---|
| 0–1 | Requirements, rules config, 24-table schema, 5 engines, workflow service | ✅ tested |
| 2 | Alembic, FastAPI (60 endpoints), demo auth + RBAC, generated API contract | ✅ tested |
| 3 | Data generator, 8 anomaly types, ground truth, validation engine, exports, reproducibility | ✅ full scale run |
| 4 | React customer portal + operations console, integrated and tested against the live backend | ✅ done |
| **5** | **AI copilot (Groq + deterministic fallback, `/api/ai/*`, copilot page, guard)** | ✅ **done** |
| 6 | Verified deployment (Vercel / Render / Neon), live PostgreSQL run | ⬜ config files only |

## Implemented and tested
See `docs/TEST_RESULTS.md`. Backend 137 tests; frontend strict typecheck + production build + 18 integration tests running against the real FastAPI server. Verified behaviours include:
- Full customer→ops→policy journey (incl. failed then successful demo payment).
- Referral review by authority, endorsement (valid / auto-rejected) and approval, renewal with endorsed terms, cancelled-policy renewal refusal, cross-customer isolation, 401/403/404/422 handling.
- Data generation + validation + export via API, route guards.
- **Underwriting AI Copilot (Phase 5)**:
  - 11 intent classes + safe read-only tools querying quotes, policies, exceptions, applicants, rules, audits.
  - Zero access or imports of `GroundTruth` in `app/ai/**` (enforced by AST tests and read-only sessions).
  - Deterministic anti-hallucination guard (`guard.py`) validating all record IDs, numbers, and forbidden claims.
  - Dual-mode architecture: Live Groq API (`openai/gpt-oss-20b`) with graceful offline fallback to deterministic templates.
  - Interactive Copilot chat workspace (`/ops/copilot`) with session persistence, suggested prompts, and clickable record pills.
  - Contextual *"Ask Copilot"* launcher buttons in Ops Quote detail, Policy detail, and Exceptions modal.
  - Append-only `AiInteraction` audit trail and Alembic migration `0003`.
  - In-memory per-user sliding-window rate limiting (429 on limit).

## Implemented but only lightly tested
- Renewal screens (customer `/my/renewals`, ops renewals list) — covered by client/API tests, not UI-render tests.
- Applicant/asset detail pages, audit log page, exception resolution modal, export download button — render paths exercised only indirectly (no dedicated UI assertions); API behind them is tested.
- "Generate dataset" button: UI test stops at the confirmation dialog; generation itself is tested via client/API.
- Background-thread generation (`background=true`) — used by the UI, never covered by an automated test.
- Mobile/responsive layout — Tailwind responsive classes only; **never viewed in a real browser or on a device** (no browser was available; verification was jsdom + build).

## Not built / not verified
- **Deployment**: `frontend/vercel.json`, `backend/Dockerfile`, `render.yaml` exist but nothing was deployed; no URL claimed. PostgreSQL DDL compiles; no live PostgreSQL run.
- Production-grade authentication (demo sessions only; no passwords, MFA, revocation, rate limiting on auth).
- Accessibility audit, browser cross-testing, load/performance testing.

## Next recommended action
Phase 6: Deployment & production verification (Vercel / Render / Neon), live PostgreSQL validation run.
