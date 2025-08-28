# ---------- 1) FRONTEND BUILD ----------
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY frontend/ .
RUN npm run build

# ---------- 2) BACKEND RUNTIME ----------
FROM python:3.13-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*
# install backend dependencies via Poetry (no virtualenv, no project install)
# copy ONLY the dependency files first to leverage Docker layer cache
COPY backend/pyproject.toml backend/poetry.lock* /tmp/dep/
RUN pip install --no-cache-dir poetry \
 && cd /tmp/dep \
 && poetry config virtualenvs.create false \
 && poetry config installer.max-workers 4 \
 && poetry install --no-interaction --no-ansi --no-root
COPY backend/ /app/backend/
COPY --from=frontend /app/frontend/dist /app/frontend_dist
ENV CHROMA_DIR=.chroma \
    PYTHONPATH=/app/backend
EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
