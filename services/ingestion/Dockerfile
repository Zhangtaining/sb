FROM python:3.11-slim

# Install system dependencies for PyAV (ffmpeg) and OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy workspace files needed for uv install
COPY pyproject.toml uv.lock* ./
COPY shared/ shared/
COPY services/ingestion/ services/ingestion/

# Install the ingestion service with its dependencies
RUN uv sync --project services/ingestion --no-dev

ENV PYTHONUNBUFFERED=1

CMD ["uv", "run", "--project", "services/ingestion", "python", "-m", "ingestion.main"]
