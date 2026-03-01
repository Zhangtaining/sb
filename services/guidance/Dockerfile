FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY shared/ shared/
COPY services/guidance/ services/guidance/

RUN uv sync --project services/guidance --no-dev

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "--project", "services/guidance", "python", "-m", "guidance.main"]
