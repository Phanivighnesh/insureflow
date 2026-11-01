"""FastAPI application factory. `uvicorn app.main:app --reload`"""
from __future__ import annotations
from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import routes_auth, routes_customer, routes_data, routes_ops, routes_ai
from app.core.config import Settings
from app.core.errors import DomainError
from app.database.session import init_db, make_engine, make_session_factory
from app.services.seed import seed_master_data


def _err(status, code, message, details=None):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details or []}})


def create_app(settings: Settings | None = None, engine=None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="InsureFlow API", version="0.2.0",
                  description="DEMO ENVIRONMENT. Customer portal + operations API over one deterministic workflow.")
    app.state.settings = settings
    app.state.engine = engine or make_engine(settings.database_url)
    app.state.session_factory = make_session_factory(app.state.engine)
    init_db(app.state.engine)               # creates missing tables (use `alembic upgrade head` for managed DBs)
    with app.state.session_factory() as s:
        seed_master_data(s)
        s.commit()

    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                       allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError):
        return _err(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        return _err(422, "VALIDATION_FAILED", "Request validation failed",
                    [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()])

    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException):
        return _err(exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.get("/api/health", tags=["health"])
    def health():
        db_status = "ok"
        try:
            from sqlalchemy import text
            with app.state.session_factory() as s:
                s.execute(text("SELECT 1"))
        except Exception as e:
            db_status = f"unhealthy: {e}"
        return {
            "status": "ok" if db_status == "ok" else "degraded",
            "service": "insureflow-api",
            "database": db_status,
            "demo_environment": True,
            "ai_provider": "groq" if settings.groq_api_key else "fallback-templates"
        }

    for r in (routes_auth.router, routes_customer.router, routes_ops.router, routes_data.router,
              routes_ai.router):
        app.include_router(r)
    return app


_app = None


def __getattr__(name):                      # lazy `app` so importing this module never touches a database
    global _app
    if name == "app":
        if _app is None:
            _app = create_app()
        return _app
    raise AttributeError(name)
