# AGENTS.md - InsureFlow (read first)

InsureFlow = AI-assisted insurance underwriting & policy-lifecycle platform: customer portal + internal ops dashboard on ONE backend/DB. Spec: `docs/REQUIREMENTS_TRACEABILITY.md`. Current state: `docs/PROJECT_STATUS.md` (always update after milestones). v2 = backend + customer portal + ops console + Underwriting AI Copilot; **deployment (Phase 6) is NOT done**.

## Stack
Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pandas/numpy/Faker, pytest. DB: SQLite (dev) / PostgreSQL. Frontend (built): React+Vite+TS strict, Tailwind, Recharts, React Router, TanStack Query (no shadcn/ui; small in-repo UI kit). AI: Groq (server-side) with deterministic fallback.

## Commands (verified)
```
cd backend && pip install -r requirements.txt
python -m pytest -q                         # backend suite (94; see docs/TEST_RESULTS.md)
(cd ../frontend && npm install && npm run typecheck && npm run build && npm test)   # frontend: boots the real backend
uvicorn app.main:app --reload               # API on :8000, Swagger at /docs
alembic upgrade head                        # managed DB schema (app also auto-creates missing tables on startup)
python -m app.data_generator --scale starter   # or --scale full [--repro-check]
python -m scripts.run_demo                  # end-to-end CLI demo (SQLite file)
# generated docs (keep in sync; tests verify the API contract):
python -m scripts.generate_api_contract --write
python -m scripts.generate_business_rules_doc > ../docs/BUSINESS_RULES.md
python -m scripts.generate_data_dictionary > ../docs/DATA_DICTIONARY.md
python -m scripts.generate_reports full
```

## Non-negotiable rules
1. Deterministic Python engines decide eligibility, risk, premium, underwriting. **LLMs only explain**; they never approve/reject/alter scores or premiums.
2. All rules live in `backend/app/core/rules_config.py`. Never hard-code thresholds elsewhere; bump `RULES_VERSION` on change and regenerate BUSINESS_RULES.md.
3. All state changes go through `services/workflow.py` (customer API, ops API and data generator share it). No parallel/mock workflows.
4. Append-only history: decisions, status history, endorsements, renewals, audit. Never overwrite or delete.
5. **Ground truth must never feed engines or the anomaly detector** (`GroundTruth` table / ground_truth.* are evaluation-only).
6. Never hard-code dashboard numbers or fabricate test/validation/deployment results.
7. Never expose API keys to the frontend; secrets via env (`.env.example`).
8. Customers must never access other customers' records (`assert_can_access_applicant`).
9. Payments are DEMO ONLY; never collect card data.
10. Keep IDs immutable and zero-padded; every FK must resolve.
11. AI Copilot is strictly read-only: never modifies database state, never decides quotes, and answers must be grounded in facts.
12. Ground truth must never feed `app/ai/**` (enforced by AST tests).
13. Anti-hallucination guard is mandatory for all LLM completions; deterministic template fallback must always work offline.

## Conventions
Engines are pure (no DB/clock/random). Services take `now` for determinism. Errors: raise `DomainError` subclasses. Add a test for every rule/behaviour change; run the full suite before finishing. Do not add microservices or unneeded dependencies.
