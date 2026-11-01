"""Alembic environment. URL precedence: -x url=... / config option > DATABASE_URL env (app settings)."""
from alembic import context
from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  (register all tables)
from app.core.config import Settings
from app.database.base import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    raw = (context.get_x_argument(as_dictionary=True).get("url")
            or config.get_main_option("sqlalchemy.url") or Settings().database_url)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg2://", 1)
    elif raw.startswith("postgresql://") and "+psycopg2" not in raw:
        return raw.replace("postgresql://", "postgresql+psycopg2://", 1)
    return raw


def run_migrations_offline():
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      render_as_batch=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _url()
    engine = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata,
                          render_as_batch=True, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
