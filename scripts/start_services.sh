#!/usr/bin/env bash
# Start all Smart Gym services locally (native, uses Mac GPU/MPS).
# Infrastructure (db/redis/minio) must already be running via: make dev-up

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Load .env
set -a; source .env; set +a

echo "Starting all services (logs in /tmp/gym-*.log)..."

start_service() {
    local name=$1
    local module=$2
    local project=$3
    uv run --project "services/$project" python -m "$module" \
        > "/tmp/gym-${name}.log" 2>&1 &
    echo "  ✓ $name (PID $! — logs: /tmp/gym-${name}.log)"
}

start_api() {
    uv run --project services/api \
        uvicorn api.main:app --host 0.0.0.0 --port 8000 \
        > /tmp/gym-api.log 2>&1 &
    echo "  ✓ api (PID $! — logs: /tmp/gym-api.log)"
}

start_service ingestion  ingestion.main  ingestion
start_service perception perception.main perception
start_service exercise   exercise.main   exercise
start_service guidance   guidance.main   guidance
start_service worker     worker.app      worker  # Celery worker
start_api

echo ""
echo "All services started."
echo "  API:  http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo ""
echo "To watch logs:   tail -f /tmp/gym-<name>.log"
echo "To stop all:     bash scripts/stop_services.sh"

# Write PIDs for stop script
pgrep -f "ingestion.main|perception.main|exercise.main|guidance.main|worker.app|uvicorn api.main" \
    > /tmp/gym-pids.txt
