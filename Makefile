.PHONY: dev-up dev-down dev-up-cv migrate test lint fmt help

# ── Environment ──────────────────────────────────────────────────────────────

# Copy .env.example to .env if .env doesn't exist
.env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example — please fill in your values"; \
	fi

# ── Docker ───────────────────────────────────────────────────────────────────

## Start infrastructure services (db, redis, minio)
dev-up: .env
	docker compose up -d db redis minio minio-init
	@echo "Infrastructure up. Run 'make migrate' to apply DB migrations."

## Start all services including CV pipeline (requires GPU for perception)
dev-up-cv: dev-up
	docker compose --profile cv up -d

## Start all services locally with native Mac GPU (faster than Docker for dev)
dev-start: dev-up
	@bash scripts/start_services.sh

## Stop all locally running services
dev-stop:
	@bash scripts/stop_services.sh

## Stop all services
dev-down:
	docker compose --profile cv down

## Stop all services and remove volumes (destructive)
dev-clean:
	docker compose --profile cv down -v

## Show service logs (usage: make logs s=api)
logs:
	docker compose logs -f $(s)

# ── Database ─────────────────────────────────────────────────────────────────

## Run Alembic migrations
migrate: .env
	@export PATH="$$HOME/.local/bin:$$PATH" && \
	  uv run --directory shared python -c "from gym_shared.db.migrations import run_migrations; run_migrations()" \
	  || uv run python scripts/setup_db.py

## Create a new Alembic migration (usage: make migration name="add_foo_table")
migration:
	@export PATH="$$HOME/.local/bin:$$PATH" && \
	  uv run --directory shared alembic -c shared/src/gym_shared/db/alembic.ini revision --autogenerate -m "$(name)"

# ── Testing ──────────────────────────────────────────────────────────────────

## Run all tests
test:
	@export PATH="$$HOME/.local/bin:$$PATH" && \
	  uv run pytest tests/ services/*/tests/ shared/tests/ -v --tb=short 2>/dev/null || \
	  uv run pytest -v --tb=short

## Run tests for a specific service (usage: make test-service s=exercise)
test-service:
	@export PATH="$$HOME/.local/bin:$$PATH" && \
	  uv run pytest services/$(s)/tests/ -v --tb=short

# ── Code Quality ─────────────────────────────────────────────────────────────

## Run ruff linter
lint:
	@export PATH="$$HOME/.local/bin:$$PATH" && \
	  uv run ruff check .

## Run ruff formatter
fmt:
	@export PATH="$$HOME/.local/bin:$$PATH" && \
	  uv run ruff format .

# ── Scripts ───────────────────────────────────────────────────────────────────

## Register a camera (usage: make register-camera id=cam-01 url=rtsp://... zone=weights)
register-camera:
	@export PATH="$$HOME/.local/bin:$$PATH" && \
	  uv run python scripts/register_camera.py --id $(id) --rtsp-url $(url) --zone $(zone)

## Register a gym member (usage: make register-person name="John Smith" goals="strength,weight_loss")
## Optional: photos=~/face_photos/john  injury="left knee"  (or skip-face=1 to skip face enrollment)
register-person:
	@export PATH="$$HOME/.local/bin:$$PATH" && \
	  uv run python scripts/register_person.py --name "$(name)" \
	    $(if $(goals),--goals "$(goals)",) \
	    $(if $(injury),--injury-notes "$(injury)",) \
	    $(if $(photos),--photos-dir "$(photos)",--skip-face)

## Setup DB from scratch (run migrations + seed)
setup-db:
	@export PATH="$$HOME/.local/bin:$$PATH" && \
	  uv run python scripts/setup_db.py

# ── Help ─────────────────────────────────────────────────────────────────────

help:
	@echo "Smart Gym System — available make targets:"
	@grep -E '^##' Makefile | sed 's/^## /  /'
