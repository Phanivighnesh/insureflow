# Frontend (React + Vite + TypeScript + Tailwind)
`frontend/src`: `api/` (types mirroring serializers; **single centralised client** `client.ts`) · `auth/AuthContext.tsx` (session + `RequireRole` guard) · `layouts/` · `components/` (UI kit, domain widgets, `PolicyView`, charts) · `pages/customer`, `pages/ops` · `lib/`.

## State & security
- TanStack Query for server state (no business data held client-side, no hard-coded metrics). 4xx are not retried.
- Demo session token stored in **`sessionStorage`** (per tab ⇒ customer and staff can be signed in side by side). 401 → session cleared and sign-in page shown. 403/404/409/422 shown as readable errors/toasts with `details`.
- `RequireRole` hides screens a role cannot use; **the backend remains the authority** for every action (the UI's authority badge is a hint only).
- No API keys in the frontend; `VITE_API_BASE` (production) is the only configuration.

## Routes → API
| Route | Role | Endpoints used |
|---|---|---|
| `/`, `/products` | public | `GET /customer/products`, `GET /customer/demo-scenarios` |
| `/login` | public | `POST /auth/demo-session` |
| `/apply/:product` | customer | `POST /customer/quotes` |
| `/quotes/:id` | customer | `GET /customer/quotes/{id}`, `POST …/accept`, `…/payment`, `/customer/payments/{id}/resolve`, `…/information` |
| `/dashboard`, `/my/quotes`, `/my/policies`, `/my/renewals`, `/policies/:id` | customer | `GET /customer/quotes|policies|renewals`, `GET /customer/policies/{id}`, `POST …/cancel|endorsements|renewals`, `POST /customer/renewals/{id}/accept|decline` |
| `/ops/login` | public | `POST /auth/demo-session` (+ staff code) |
| `/ops` | staff | `GET /dashboard/summary|underwriting|renewals|exceptions` |
| `/ops/applicants[/:id]`, `/ops/assets[/:id]` | staff | `GET /applicants`, `/assets` (+ detail) |
| `/ops/quotes[/:id]`, `/ops/underwriting` | staff | `GET /quotes`, `/quotes/{id}`, `/quotes/{id}/audit`, `POST /quotes/{id}/evaluate`, `GET /underwriting/pending`, `POST /underwriting/{decision_id}/approve|reject|request-information` |
| `/ops/copilot` | staff | `GET /api/ai/status`, `POST /api/ai/chat`, `POST /api/ai/explain-decision`, `POST /api/ai/explain-exception` |
| `/ops/policies[/:id]`, `/ops/endorsements`, `/ops/renewals` | staff | `GET/POST /policies…`, `/endorsements…`, `/renewals…` |
| `/ops/exceptions`, `/ops/audit` | staff | `GET /exceptions`, `POST /exceptions/{id}/resolution`, `GET /audit` |
| `/ops/data` | staff (generate: admin; validation/export: reviewer+admin) | `GET /data/status`, `POST /data/generate`, `POST /validation/run`, `GET /data/validation|reproducibility|export`, `POST /data/reproducibility-check` |

## Build / config
`npm run dev` (Vite, proxy `/api` → `VITE_PROXY_TARGET`, default `http://localhost:8000`) · `npm run build` (typecheck + production build; routes are code-split, charts load on demand) · `.env.test` points tests at the backend started by `tests/globalSetup.ts` · `vercel.json` = SPA rewrite (unverified deployment).
