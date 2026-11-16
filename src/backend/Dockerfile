# Backend image: FastAPI + LangGraph agent (+ Playwright's Chromium if it's in requirements.txt).
# Build context is the REPO ROOT (requirements.txt lives there), see docker-compose.yml.
FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Same layout as the repo (/code = repo root), so config.py's ROOT_DIR = parents[3] still works.
WORKDIR /code

# 1. Dependencies first: cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt \
 && if pip show playwright >/dev/null 2>&1; then \
        playwright install --with-deps chromium; \
    else \
        echo "playwright not in requirements.txt: skipping browser install"; \
    fi

# 2. App code (data/ is mounted at runtime, not baked in).
COPY src/backend/ src/backend/

# 3. Don't run as root.
RUN useradd --create-home --uid 1000 app \
 && mkdir -p src/backend/data \
 && chown -R app:app /code
USER app

WORKDIR /code/src/backend
EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"

ENTRYPOINT ["sh", "./docker-entrypoint.sh"]