# Local Agent (Google Antigravity) Handoff
Read `AGENTS.md`, `docs/PROJECT_STATUS.md`, `docs/REQUIREMENTS_TRACEABILITY.md` first. Produced WITHOUT Claude Code; only items marked verified were executed (Linux sandbox, Python 3.12, SQLite).

| # | Step | Command | Status |
|---|---|---|---|
| 1 | Backend deps | `cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` | ✅ verified |
| 2 | Frontend deps | `cd frontend && npm install` | ✅ verified |
| 3 | Env | `cp .env.example .env` (set `SESSION_SECRET`, `STAFF_ACCESS_CODE`) | ✅ |
| 4 | Init SQLite | automatic on API start (`create_all` + seed) | ✅ |
| 5 | Migrations | `cd backend && alembic upgrade head` (uses `DATABASE_URL`; or `alembic -x url=sqlite:///x.db upgrade head`) | ✅ SQLite; ⬜ PostgreSQL never run live |
| 6 | Generate data | `python -m app.data_generator --seed 20261022 --scale starter` (or `full`; `--repro-check`) | ✅ both scales run |
| 7 | Start backend | `cd backend && uvicorn app.main:app --reload --port 8000` → http://localhost:8000/docs | ✅ verified (real uvicorn) |
| 8 | Start frontend | `cd frontend && npm run dev` → http://localhost:5173 (proxies /api to :8000) | ✅ verified (dev server + proxy via curl) |
| 9 | Tests | `cd backend && python -m pytest -q` (94) and `cd frontend && npm test` (12) | ✅ see `docs/TEST_RESULTS.md` |
| 10 | E2E demo | `python -m scripts.run_demo` (CLI) and the API journey in `tests/test_api.py` | ✅ |

## Try the API manually
```
curl -s -X POST localhost:8000/api/auth/demo-session -H 'content-type: application/json' -d '{"role":"CUSTOMER"}'
curl -s localhost:8000/api/customer/demo-scenarios        # prefilled inputs; POST one to /api/customer/quotes with the Bearer token
curl -s -X POST localhost:8000/api/auth/demo-session -H 'content-type: application/json' -d '{"role":"ADMINISTRATOR","access_code":"insureflow-demo"}'
```
## Suggested next tasks
1. **Phase 5 AI copilot** — `backend/app/ai` (safe query tools → grounded context → Groq, deterministic template fallback; the LLM must never decide), `/api/ai/chat|explain-decision|explain-exception`, a copilot page in `frontend/src/pages/ops`, and tests (including fallback and the "LLM cannot override decisions" guarantee).
2. **Phase 6** — deploy (Render + Neon + Vercel), run Alembic against live PostgreSQL, verify URLs, set `SESSION_SECRET` / `STAFF_ACCESS_CODE` / `CORS_ORIGINS` / `VITE_API_BASE`.
3. Visual/responsive/accessibility review in a real browser; UI tests for renewal screens.
Do not change engine behaviour without updating tests and regenerating docs (commands in root AGENTS.md). Routes must stay transactional (`TransactionalRoute`).
