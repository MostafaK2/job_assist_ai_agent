"""Alembic: creates and updates OUR tables (models.py). Never touches LangGraph's checkpoint tables."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import APP_DATABASE_URL
from app.db import models  # noqa: F401  (registers the tables on Base.metadata)
from app.db.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Tables created and managed by LangGraph's Postgres checkpointer (checkpointer.setup()).
# Without this, autogenerate sees them as "unknown" and writes a migration that DROPS them.
LANGGRAPH_TABLE_PREFIX = "checkpoint"


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and name.startswith(LANGGRAPH_TABLE_PREFIX):
        return False
    if type_ in {"index", "unique_constraint", "foreign_key_constraint"}:
        table = getattr(obj, "table", None)
        if table is not None and table.name.startswith(LANGGRAPH_TABLE_PREFIX):
            return False
    return True


def configure(**kwargs):
    context.configure(
        target_metadata=target_metadata,
        include_object=include_object,
        compare_type=True,            # notice column type changes too
        compare_server_default=True,  # and default value changes
        **kwargs,
    )


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it."""
    configure(url=APP_DATABASE_URL, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    # The URL comes from .env (APP_DATABASE_URL), not alembic.ini, so no password is ever committed.
    engine = create_async_engine(APP_DATABASE_URL, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())