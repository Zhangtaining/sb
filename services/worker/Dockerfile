FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_SYSTEM_PYTHON=1

COPY pyproject.toml uv.lock ./
COPY shared/ shared/
COPY services/worker/ services/worker/
RUN uv sync --project services/worker --no-dev

WORKDIR /app/services/worker
CMD ["uv", "run", "celery", "-A", "worker.app", "worker", "--loglevel=info", "--concurrency=2"]
