#!/bin/sh
set -e

# 1. Create/update our tables. Safe on every start.
#    LangGraph's checkpoint* tables are created by checkpointer.setup() when the app starts.
echo "Running database migrations..."
alembic upgrade head

# 2. ONE worker on purpose: drafts and approvals live in memory (tools/apply.py).
echo "Starting API on :8000"
# Caddy tells the backend “the user came in over HTTPS” through an X-Forwarded-Proto header. By default, uvicorn only trusts that header from 127.0.0.1, and Caddy is in a different container. Trusting it from anywhere is safe here because the backend isn’t published, so only Caddy and the frontend can reach it
exec uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips="*"