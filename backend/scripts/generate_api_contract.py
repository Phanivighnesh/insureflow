"""Generates docs/API_CONTRACT.md and docs/openapi.json from the REAL FastAPI routes (so they cannot drift).
Usage:  python -m scripts.generate_api_contract --write      (a pytest verifies the committed files are current)"""
import json, os, sys

from fastapi.routing import APIRoute

from app.api.deps import STAFF
from app.core.config import Settings
from app.database.session import make_engine
from app.main import create_app

DOCS = os.path.join(os.path.dirname(__file__), "..", "..", "docs")
INTRO = """# API Contract (generated from the implemented FastAPI routes - do not edit by hand)

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
"""


def build():
    app = create_app(Settings(database_url="sqlite:///:memory:"), make_engine("sqlite:///:memory:"))
    from app.api import routes_auth, routes_customer, routes_data, routes_ops, routes_ai
    rows = []
    # routes registered on the app itself + each included router (their paths already carry the router prefix)
    all_routes = [r for r in app.routes if isinstance(r, APIRoute)]
    for mod in (routes_auth, routes_customer, routes_ops, routes_data, routes_ai):
        all_routes += [r for r in mod.router.routes if isinstance(r, APIRoute)]
    for rr in all_routes:
        if True:
            if not rr.path.startswith("/api"):
                continue
            roles = "public"
            for d in rr.dependant.dependencies:
                allowed = getattr(d.call, "allowed_roles", None)
                if allowed:
                    roles = "STAFF" if set(allowed) == set(STAFF) else ", ".join(allowed)
                    break
                if d.call.__name__ == "current_actor":
                    roles = "any authenticated"
            for m in sorted(rr.methods - {"HEAD", "OPTIONS"}):
                rows.append((rr.path, m, roles, (rr.endpoint.__doc__ or "").strip().split("\n")[0], rr.endpoint.__name__))
    return app, sorted(rows, key=lambda x: (x[0], x[1]))


def render():
    app, rows = build()
    out, group = [INTRO], None
    for path, m, roles, doc, name in rows:
        g = path.split("/")[2] if len(path.split("/")) > 2 else "root"
        g = "customer" if g == "customer" else ("data/validation" if g in ("data", "validation") else ("auth" if g == "auth" else ("health" if g == "health" else "operations")))
        if g != group:
            group = g
            out.append(f"\n## {group}\n\n| Method | Path | Access | Handler / summary |\n|---|---|---|---|")
        out.append(f"| {m} | `{path}` | {roles} | `{name}` {('- ' + doc) if doc else ''} |")
    out.append(f"\n_{len(rows)} endpoints._ Request/response schemas: see `docs/openapi.json`.\n")
    return "\n".join(out), json.dumps(app.openapi(), indent=1, sort_keys=True) + "\n"


if __name__ == "__main__":
    md, oa = render()
    if "--write" in sys.argv:
        open(os.path.join(DOCS, "API_CONTRACT.md"), "w").write(md)
        open(os.path.join(DOCS, "openapi.json"), "w").write(oa)
        print("written", len(md.splitlines()), "lines")
    else:
        print(md)
