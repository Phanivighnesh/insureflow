# frontend/AGENTS.md
**Status: built (v2).** React 18 + Vite + TypeScript (strict) + Tailwind 3 + React Router 6 + TanStack Query 5 + Lucide + Recharts. Docs: `docs/FRONTEND.md`, `docs/AI_COPILOT.md`, `docs/API_CONTRACT.md`, `docs/openapi.json`, `docs/DEMO_GUIDE.md`.

## Commands
`npm install` · `npm run dev` (proxy /api -> :8000) · `npm run typecheck` · `npm run build` · `npm test` (boots the real backend; needs backend Python deps).

## Rules
- All HTTP goes through `src/api/client.ts` (`makeApi`). Never call `fetch` elsewhere; never invent endpoints - check `docs/openapi.json` (request bodies reject unknown fields).
- No hard-coded business data, premiums or metrics; UI renders what the API returns. Customers must never see a premium for DECLINED quotes (API already withholds it).
- Backend is the authority for authorisation; `RequireRole` and the authority badge are UX only.
- Payment UI must stay clearly labelled DEMO. No card fields. No secrets in the frontend; configuration is `VITE_API_BASE` only.
- New screens need loading / error / empty states, and confirmation dialogs for destructive or irreversible actions.
- AI Copilot (`/ops/copilot`) is staff-only, read-only, and provides record references linking to real entities.
- When changing UI, run the full suite 2-3 times (tests share one backend; use unique tags, never global counts). Prefer `data-testid`/`data-status` attributes over text queries when text can appear in several places.
- Pending: UI-render tests for renewal screens, real-browser responsive/a11y review, Phase 6 deployment.
