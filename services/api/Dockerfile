FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_SYSTEM_PYTHON=1

# Install workspace packages
COPY pyproject.toml uv.lock ./
COPY shared/ shared/
COPY services/api/ services/api/
RUN uv sync --project services/api --no-dev

WORKDIR /app/services/api
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
