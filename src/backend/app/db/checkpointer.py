"""The agent's memory: LangGraph's Postgres checkpointer, on a shared connection pool.

Opened once when the server starts (see app/api/main.py) and closed when it stops.
"""
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.db.engine import plain_postgres_url


async def open_checkpointer() -> tuple[AsyncPostgresSaver, AsyncConnectionPool]:
    pool = AsyncConnectionPool(
        conninfo=plain_postgres_url(),
        min_size=1,
        max_size=10,
        # Settings LangGraph's Postgres checkpointer requires:
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    )
    await pool.open(wait=True, timeout=10)  # fail fast if Postgres isn't running

    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()  # creates/updates LangGraph's checkpoint* tables; safe on every start
    return checkpointer, pool