# Testing Guide
```
cd backend && pip install -r requirements.txt
python -m pytest -q                              # everything (~1 min; generator tests regenerate starter datasets)
python -m pytest tests/test_engines.py -q        # pure engine rules
python -m pytest tests/test_workflow.py -q       # DB-backed lifecycle (service layer)
python -m pytest tests/test_api.py -q            # auth, RBAC, cross-customer isolation, journeys, migrations, API-contract sync, CORS
python -m pytest tests/test_generator.py -q      # volumes, anomalies, detector vs ground truth, reproducibility
python -m pytest tests/test_api_data.py -q       # generation/validation/export endpoints
```
Fixtures (`tests/conftest.py`): in-memory seeded DB; `api` = TestClient on an isolated in-memory app; `login()` helper and `cust_a/cust_b/analyst/reviewer/admin` session headers; fixed clock `NOW=2026-03-01` for service tests.

Mutation-check technique: temporarily break a rule (e.g. remove an ownership check, disable an acceptance check, add wall-clock to RNG seeding), confirm tests fail, restore. Done for: decline threshold, base rate, payment prerequisite, route ownership, role guard, detector acceptance rule, RNG determinism.

## Frontend
```
cd frontend && npm install
npm run typecheck        # strict TS
npm run build            # tsc + vite build
npm test                 # vitest: tests/journey.test.ts (client vs live API) + tests/ui.test.tsx (React UI vs live API)
```
`tests/globalSetup.ts` starts `python3 -m uvicorn app.main:app` from `../backend` on port 8791 with a temporary SQLite DB and staff code `fe-test-code`; it is torn down afterwards (requires Python deps installed). `.env.test` points the UI at that port. Files run sequentially against one shared server, so tests use unique tags/customers and never rely on global counts. UI tests persist the demo session in `sessionStorage` between tests on purpose (sign out via the UI to switch role).

Not covered: live PostgreSQL execution, real browsers/responsive layouts, Groq integration (not built), load/performance, background-thread generation under concurrent requests (tests run generation synchronously).
