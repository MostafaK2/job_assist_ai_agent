"""Database connection for our own tables (SQLAlchemy, async, psycopg driver)."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import APP_DATABASE_URL

engine = create_async_engine(APP_DATABASE_URL, pool_pre_ping=True)

# expire_on_commit=False: objects stay readable after commit (handy in API responses)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def plain_postgres_url(url: str = APP_DATABASE_URL) -> str:
    """'postgresql+psycopg://…' (SQLAlchemy's format) → 'postgresql://…' (psycopg's / LangGraph's)."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)

async def get_session():
    """FastAPI dependency: one database session per request, closed afterwards."""
    async with SessionLocal() as session:
        yield session