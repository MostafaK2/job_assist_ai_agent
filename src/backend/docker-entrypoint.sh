#!/bin/sh
set -e

# 1. Create/update our tables. Safe on every start.
#    LangGraph's checkpoint* tables are created by checkpointer.setup() when the app starts.
echo "Running database migrations..."
alembic upgrade head

# 2. ONE worker on purpose: drafts and approvals live in memory (tools/apply.py).
echo "Starting API on :8000"
exec uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers