"""Engine/session factories. SQLite (dev) and PostgreSQL share the same SQLAlchemy models."""
from __future__ import annotations
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.database.base import Base


def make_engine(url: str | None = None):
    url = url or settings.database_url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and "+psycopg2" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, future=True, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):          # enforce foreign keys in SQLite
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
    return engine


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=True, expire_on_commit=False, future=True)


def init_db(engine) -> None:
    import app.models  # noqa: F401  (register tables)
    Base.metadata.create_all(engine)
