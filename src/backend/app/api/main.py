"""FastAPI app. Run from src/backend:

    uvicorn app.api.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.agent import build_agent
from app.api.assistant import router as assistant_router
from app.db.checkpointer import open_checkpointer
from app.db.engine import engine
from app.api.threads import router as threads_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect the agent's memory to Postgres, then build the agent once.
    checkpointer, pool = await open_checkpointer()
    app.state.agent = build_agent(checkpointer=checkpointer)
    app.state.checkpointer = checkpointer
    yield
    # Shutdown: close database connections cleanly.
    await pool.close()
    await engine.dispose()


app = FastAPI(title="Job Assist API", lifespan=lifespan)
app.include_router(assistant_router, prefix="/api")
app.include_router(threads_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}