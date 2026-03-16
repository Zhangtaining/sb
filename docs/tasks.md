# Phase 1 Tasks — Smart Gym System

> Phase 1 Goal: Single camera, anonymous tracking, rep counting, form alerts, LLM audio guidance on phone, movement replay clips, and training stats.

> **After completing every task:** run all verification checks → `git status` → `git add <files>` → commit with `feat(<scope>): <desc>\n\nTask: #[ID]` → `git push origin main` → update status to `COMPLETE` → append to `docs/progress.md`.

---

## T01: Monorepo Scaffold — Directory Structure, Makefile, .env.example

- **Status:** `COMPLETE`
- **Description:** Create the top-level project skeleton. Initialize `uv` workspace. Create all service/shared directory stubs. Write `Makefile` with `dev-up`, `dev-down`, `migrate`, `test` targets. Write `.env.example` with all required variables.
- **Why:** Every other task depends on the repo structure existing. Must be the first task done.
- **Expected Results:** Running `make dev-up` starts the Docker services (even if services are empty). All directories from PLAN.md exist. `.env.example` documents every required env var.
- **Verification:**
  - [ ] `make dev-up` starts without errors (infrastructure containers only)
  - [ ] `make dev-down` stops cleanly
  - [ ] All top-level directories exist: `services/`, `shared/`, `ml/`, `scripts/`, `infrastructure/`, `docs/`
  - [ ] `.env.example` is present and documents DB URL, Redis URL, MinIO creds, Anthropic API key
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `chore(scaffold): init monorepo structure and Makefile\n\nTask: #T01`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** None
- **Notes:** Use `uv` (not pip/poetry). Each service will have its own `pyproject.toml`. The root `pyproject.toml` defines the workspace. Service stubs can be empty `__init__.py` files for now.

---

## T02: Shared Package — Settings, Logging, Redis Client

- **Status:** `COMPLETE`
- **Description:** Create the `shared/` internal Python package (`gym_shared`). Implement: Pydantic `BaseSettings` for shared config (reads from `.env`), `structlog` structured logging setup, async Redis client factory.
- **Why:** All services import from `gym_shared`. Must exist before any service code is written.
- **Expected Results:** `gym_shared` package installable via `uv`. `from gym_shared.redis_client import get_redis` works. `from gym_shared.settings import Settings` works.
- **Verification:**
  - [ ] `uv run python -c "from gym_shared.settings import Settings; print(Settings())"` succeeds
  - [ ] `uv run python -c "from gym_shared.redis_client import get_redis"` succeeds
  - [ ] Logging outputs structured JSON when `LOG_FORMAT=json`
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(shared): add settings, logging, and Redis client\n\nTask: #T02`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T01
- **Notes:** `shared/src/gym_shared/settings.py` — use `model_config = SettingsConfigDict(env_file=".env")`. Redis client should use `redis.asyncio`.

---

## T03: Shared Package — SQLAlchemy ORM Models

- **Status:** `COMPLETE`
- **Description:** Implement all Phase 1 SQLAlchemy 2.0 async ORM models in `shared/src/gym_shared/db/models.py`: `Camera`, `Track`, `GymSession`, `ExerciseSet`, `RepEvent` (TimescaleDB hypertable), `PoseFrame` (TimescaleDB hypertable).
- **Why:** All services that read/write the database import these models. Must be defined before migrations.
- **Expected Results:** All 6 models defined using `Mapped[T]` / `mapped_column()` style. Relationships defined between models. `pgvector` `Vector` type used where specified in PLAN.md.
- **Verification:**
  - [ ] `uv run python -c "from gym_shared.db.models import Camera, Track, GymSession, ExerciseSet, RepEvent, PoseFrame"` succeeds with no errors
  - [ ] All foreign key relationships are defined (Track → GymSession, ExerciseSet → GymSession, RepEvent → ExerciseSet, etc.)
  - [ ] `Vector(256)` type used for `Track.reid_embedding`
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(shared): add SQLAlchemy ORM models for Phase 1\n\nTask: #T03`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T02
- **Notes:** `RepEvent` and `PoseFrame` will be converted to TimescaleDB hypertables in the migration (T04), not in the ORM model itself. Use `pgvector.sqlalchemy` for Vector columns.

---

## T04: Shared Package — Alembic Migrations + DB Session Factory

- **Status:** `COMPLETE`
- **Description:** Set up Alembic for async migrations. Write the initial migration that: enables `pgvector` and `timescaledb` extensions, creates all Phase 1 tables, converts `rep_events` and `pose_frames` to TimescaleDB hypertables. Implement async SQLAlchemy session factory in `shared/src/gym_shared/db/session.py`.
- **Why:** Services cannot persist data until the schema exists. `make migrate` must work.
- **Expected Results:** `make migrate` runs cleanly against a fresh PostgreSQL+TimescaleDB container. All tables exist. `rep_events` and `pose_frames` are hypertables.
- **Verification:**
  - [ ] `make migrate` exits 0
  - [ ] `psql` shows all 6 tables created
  - [ ] `SELECT * FROM timescaledb_information.hypertables` shows `rep_events` and `pose_frames`
  - [ ] `SELECT * FROM pg_extension WHERE extname IN ('vector','timescaledb')` returns both rows
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(shared): add Alembic migrations and DB session factory\n\nTask: #T04`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T03, T05
- **Notes:** Use `alembic.ini` with async driver (`asyncpg`). Hypertable conversion: `SELECT create_hypertable('rep_events', 'time');`. Migration must be idempotent (use `IF NOT EXISTS`).

---

## T05: Docker Compose — Infrastructure Services

- **Status:** `COMPLETE`
- **Description:** Write `docker-compose.yml` defining: PostgreSQL 16 + TimescaleDB, Redis 7, MinIO, Nginx. Write `infrastructure/nginx/nginx.conf`. All services should have health checks. Volumes for data persistence.
- **Why:** All development and testing depends on these containers being available via `make dev-up`.
- **Expected Results:** `make dev-up` starts all 4 infrastructure containers healthy. PostgreSQL accessible on port 5432, Redis on 6379, MinIO on 9000/9001.
- **Verification:**
  - [ ] `docker compose ps` shows all containers as `healthy`
  - [ ] `psql -h localhost -U gym -d gymdb -c '\l'` connects successfully
  - [ ] `redis-cli ping` returns `PONG`
  - [ ] MinIO console accessible at `http://localhost:9001`
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `chore(infra): add docker-compose for infrastructure services\n\nTask: #T05`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T01
- **Notes:** Use `timescale/timescaledb-ha:pg16` image (includes pgvector). MinIO env vars: `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`. Create default bucket `gym-clips` on startup via MinIO init container or mc client script.

---

## T06: Shared Package — Redis Streams Event Schemas

- **Status:** `COMPLETE`
- **Description:** Define all Pydantic v2 event schemas used on Redis Streams in `shared/src/gym_shared/events/schemas.py`. Write helper publisher in `shared/src/gym_shared/events/publisher.py` that serializes and `XADD`s to a stream. Implement a consumer helper for `XREAD`/`XREADGROUP`.
- **Why:** Ingestion, perception, exercise, and guidance services all communicate via Redis Streams. Having typed schemas prevents silent data corruption between services.
- **Expected Results:** Schemas defined: `FrameMessage`, `PerceptionEvent`, `RepCountedEvent`, `FormAlertEvent`, `GuidanceMessage`. Publisher and consumer helpers work.
- **Verification:**
  - [ ] `from gym_shared.events.schemas import FrameMessage, PerceptionEvent, FormAlertEvent` succeeds
  - [ ] Round-trip test: publish a `PerceptionEvent`, read it back, parse it — values match
  - [ ] All schemas have `model_config = ConfigDict(frozen=True)`
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(shared): add Redis Streams event schemas and publisher\n\nTask: #T06`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T02
- **Notes:** Use `model.model_dump_json()` for serialization to Redis. Stream names follow convention `{domain}:{camera_id}` (e.g., `frames:cam-01`).

---

## T07: Ingestion Service — Scaffold (pyproject.toml, Dockerfile, Config)

- **Status:** `COMPLETE`
- **Description:** Create `services/ingestion/` service scaffold: `pyproject.toml` (depends on `gym_shared`, `av`, `opencv-python-headless`), `Dockerfile` (Python 3.11 slim base), `src/ingestion/config.py` (Pydantic settings for camera list, FPS, JPEG quality), `src/ingestion/main.py` (entry point stub).
- **Why:** Scaffold must exist before implementing the camera reader logic.
- **Expected Results:** `docker compose build ingestion` succeeds. Service starts and logs "Ingestion service starting" then exits cleanly (stub).
- **Verification:**
  - [ ] `docker compose build ingestion` exits 0
  - [ ] `uv run --directory services/ingestion python -m ingestion.main` starts without import errors
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `chore(ingestion): add service scaffold\n\nTask: #T07`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T01, T02, T05
- **Notes:** Add `ingestion` service to `docker-compose.yml` but set `restart: "no"` for now.

---

## T08: Ingestion Service — Camera Reader (RTSP → Frame Buffer)

- **Status:** `COMPLETE`
- **Description:** Implement `services/ingestion/src/ingestion/camera_reader.py`. One thread per camera that opens an RTSP stream via `av` (hardware H.264 decode preferred, fallback to software). Reads frames, downsamples to configured FPS (default 15), compresses to JPEG at quality 85. Pushes compressed frames to an in-memory `queue.Queue` (the frame buffer).
- **Why:** This is the entry point for all video data into the system.
- **Expected Results:** `CameraReader` class that accepts a `CameraConfig` and a `Queue`. Runs as a daemon thread. Handles reconnection on stream drop (retry with exponential backoff, max 30s).
- **Verification:**
  - [ ] With a test RTSP stream (or local video file path), frames appear in the queue at ~15 FPS
  - [ ] Disconnecting the stream triggers reconnection attempt (logged)
  - [ ] Unit test: mock stream, verify queue receives expected number of frames
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(ingestion): add RTSP camera reader with reconnection\n\nTask: #T08`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T07
- **Notes:** For testing without a real camera, `av` can open a local `.mp4` file via `av.open("test.mp4")`. Rolling 15-second buffer (225 frames at 15 FPS) kept as a `collections.deque(maxlen=225)` for use by the video clip worker later.

---

## T09: Ingestion Service — Frame Publisher (Queue → Redis Stream)

- **Status:** `COMPLETE`
- **Description:** Implement `services/ingestion/src/ingestion/frame_publisher.py`. Reads frames from the `CameraReader` queue, serializes them as `FrameMessage`, and `XADD`s to `frames:{camera_id}` Redis Stream with `MAXLEN ~100` (trimming cap to prevent memory blow-up).
- **Why:** The perception service consumes from this stream. Without the publisher, the pipeline cannot flow.
- **Expected Results:** Frames appear in Redis Stream `frames:cam-01` at ~15 FPS. Stream length stays bounded at ~100 entries under load.
- **Verification:**
  - [ ] `redis-cli XLEN frames:cam-01` stabilizes around 100 under continuous load
  - [ ] `redis-cli XRANGE frames:cam-01 - + COUNT 1` returns a valid `FrameMessage`-shaped entry
  - [ ] Integration test: start ingestion with a test video, verify frames appear in Redis
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(ingestion): add frame publisher to Redis Streams\n\nTask: #T09`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T08, T06
- **Notes:** Use `XADD frames:{camera_id} MAXLEN ~ 100 * field value ...`. The `~` makes trimming approximate (faster). Base64-encode jpeg bytes for Redis string storage.

---

## T10: Scripts — Register Camera CLI

- **Status:** `COMPLETE`
- **Description:** Implement `scripts/register_camera.py`. CLI tool (argparse or click) that inserts a new `Camera` record into PostgreSQL. Accepts: `--id`, `--rtsp-url`, `--zone`, `--description`. Prints the created camera ID on success.
- **Why:** Cameras must be registered in the DB before the ingestion service can be started for them. Used in Phase 1 verification step.
- **Expected Results:** Running `python scripts/register_camera.py --id cam-01 --rtsp-url rtsp://... --zone weights` creates a row in the `cameras` table.
- **Verification:**
  - [ ] Script runs without error against a running DB
  - [ ] `SELECT * FROM cameras WHERE id = 'cam-01'` returns the inserted row
  - [ ] Running it twice with the same `--id` prints a clear error (unique constraint)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(scripts): add register_camera CLI\n\nTask: #T10`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T04

---

## T11: Scripts — DB Setup Script

- **Status:** `COMPLETE`
- **Description:** Implement `scripts/setup_db.py`. Runs Alembic migrations programmatically and seeds any required initial data (e.g., a default `gym-clips` MinIO bucket creation check). Used in `make migrate` target.
- **Why:** New developers and CI need a single command to get a fresh DB ready.
- **Expected Results:** `python scripts/setup_db.py` on a blank DB runs all migrations and prints success.
- **Verification:**
  - [ ] `python scripts/setup_db.py` exits 0 on a fresh DB
  - [ ] Re-running is idempotent (no errors on second run)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(scripts): add setup_db script\n\nTask: #T11`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T04

---

## T12: Perception Service — Scaffold (pyproject.toml, Dockerfile, Config)

- **Status:** `COMPLETE`
- **Description:** Create `services/perception/` scaffold: `pyproject.toml` (depends on `gym_shared`, `ultralytics`, `torchreid`, `opencv-python-headless`), `Dockerfile` (CUDA-capable base image: `pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime`), `src/perception/config.py`, `src/perception/main.py` stub.
- **Why:** Scaffold must exist before implementing detection/tracking logic.
- **Expected Results:** `docker compose build perception` succeeds.
- **Verification:**
  - [ ] `docker compose build perception` exits 0
  - [ ] `import ultralytics; import torchreid` succeeds inside the container
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `chore(perception): add service scaffold\n\nTask: #T12`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T01, T02, T05
- **Notes:** The CUDA image makes this build large (~8GB). Use multi-stage build to keep it reasonable. Download model weights separately via `scripts/download_models.sh` (not baked into image).

---

## T13: Perception Service — Person Detector (YOLOv11-pose)

- **Status:** `COMPLETE`
- **Description:** Implement `services/perception/src/perception/detector.py`. Wraps `ultralytics` YOLOv11-pose model. `detect(frame: np.ndarray) -> list[Detection]` returns bounding boxes + 17 keypoints per detected person. Uses nano (`yolo11n-pose.pt`) by default, configurable.
- **Why:** Person detection + pose keypoints are the foundation for tracking, ReID, and exercise analysis.
- **Expected Results:** `Detector` class that loads the model once at init. Returns a list of `Detection(bbox, keypoints, confidence)` per frame. Runs at >15 FPS on GPU for a single camera stream.
- **Verification:**
  - [ ] Unit test: run detector on a static test image containing a person — at least 1 detection returned with 17 keypoints
  - [ ] `keypoints` contains 17 entries each with `(x, y, visibility)`
  - [ ] Model runs on CUDA if available, CPU otherwise (no crash on CPU-only machine)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(perception): add YOLOv11-pose person detector\n\nTask: #T13`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T12
- **Notes:** Use `model.predict(frame, classes=[0], verbose=False)` — class 0 is "person" in COCO. Keypoints are in pixel coordinates; normalize to [0,1] relative to the frame before passing downstream.

---

## T14: Perception Service — Intra-Camera Tracker (ByteTrack)

- **Status:** `COMPLETE`
- **Description:** Implement `services/perception/src/perception/tracker.py`. Wraps Ultralytics' built-in ByteTrack tracker. Assigns a stable `local_track_id` to each detected person across frames within a single camera.
- **Why:** Without tracking, each frame gives anonymous detections with no continuity. Tracking lets the exercise service accumulate rep counts per person over time.
- **Expected Results:** `Tracker` class that accepts a list of `Detection` objects per frame and returns `TrackedDetection` objects with a stable `local_track_id` that persists across frames.
- **Verification:**
  - [ ] Unit test: feed 30 frames from a test video — same person gets the same `track_id` throughout
  - [ ] New person entering frame gets a new ID; exiting and re-entering after 5s gets a new ID (expected ByteTrack behavior)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(perception): add ByteTrack intra-camera tracker\n\nTask: #T14`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T13
- **Notes:** Ultralytics ByteTrack is available via `model.track()` or can be instantiated directly. Set `track_high_thresh=0.5`, `track_low_thresh=0.1`, `new_track_thresh=0.6`.

---

## T15: Perception Service — ReID Feature Extractor (OSNet)

- **Status:** `COMPLETE`
- **Description:** Implement `services/perception/src/perception/reid_extractor.py`. Loads OSNet-x1.0 via `torchreid`. `extract(person_crop: np.ndarray) -> np.ndarray` returns a 256-d L2-normalized embedding vector.
- **Why:** These embeddings are the basis for cross-camera person re-identification in Phase 2. Must be computed in Phase 1 so the data is available when Phase 2 builds on top.
- **Expected Results:** `ReIDExtractor` class. Accepts an RGB crop of a person (any size), returns a `np.ndarray` of shape `(256,)`, L2-normalized.
- **Verification:**
  - [ ] Unit test: two crops of the same person from different angles → cosine similarity > 0.7
  - [ ] Two crops of different people → cosine similarity < 0.5
  - [ ] `np.linalg.norm(embedding)` ≈ 1.0 (L2-normalized)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(perception): add OSNet ReID feature extractor\n\nTask: #T15`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T12
- **Notes:** Input to OSNet must be resized to 256×128 (H×W) and normalized. Use `torchreid.data.transforms.build_transforms(height=256, width=128)[1]` for test transforms. Run in `torch.no_grad()`.

---

## T16: Perception Service — Pipeline (Compose + Publish)

- **Status:** `COMPLETE`
- **Description:** Implement `services/perception/src/perception/pipeline.py` and wire up `main.py`. The pipeline: consumes frames from `frames:{camera_id}` Redis Stream (via `XREADGROUP`), runs Detector → Tracker → ReIDExtractor per frame, publishes a `PerceptionEvent` per tracked person to `perceptions:{camera_id}` Redis Stream.
- **Why:** This is the core CV pipeline that transforms raw video frames into structured detections consumed by downstream services.
- **Expected Results:** With ingestion running, `redis-cli XRANGE perceptions:cam-01 - + COUNT 1` returns a valid `PerceptionEvent` with `track_id`, `bbox`, `keypoints[33]`, `reid_embedding[256]`.
- **Verification:**
  - [ ] Integration test: start ingestion + perception with a test video, verify `perceptions:cam-01` receives events
  - [ ] Each event has all required fields and correct array dimensions
  - [ ] Pipeline processes frames at ≥10 FPS on GPU (log throughput on startup)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(perception): wire up full pipeline and Redis Stream publisher\n\nTask: #T16`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T13, T14, T15, T06
- **Notes:** Use `XREADGROUP` with a consumer group `perception-workers` so multiple workers can partition camera streams in the future. Create the consumer group with `XGROUP CREATE ... MKSTREAM` on startup if it doesn't exist.

---

## T17: Exercise Service — Scaffold (pyproject.toml, Dockerfile, Config)

- **Status:** `COMPLETE`
- **Description:** Create `services/exercise/` scaffold: `pyproject.toml` (depends on `gym_shared`, `numpy`, `scipy`, `pyyaml`), `Dockerfile` (CPU-only, Python 3.11 slim), `src/exercise/config.py`, `src/exercise/main.py` stub.
- **Why:** Scaffold must exist before implementing exercise analysis logic.
- **Expected Results:** `docker compose build exercise` succeeds.
- **Verification:**
  - [ ] `docker compose build exercise` exits 0
  - [ ] `import numpy, scipy, yaml` succeeds inside the container
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `chore(exercise): add service scaffold\n\nTask: #T17`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T01, T02, T05

---

## T18: Exercise Service — Exercise Definitions YAML

- **Status:** `COMPLETE`
- **Description:** Create `services/exercise/data/exercises.yaml` defining the 4 Phase 1 exercises: squat, push-up, bicep curl, lateral raise. Each definition includes: primary joint pair for rep counting, `up_angle_threshold`, `down_angle_threshold`, form checks (joint, min_angle, max_angle, alert_message).
- **Why:** The exercise registry loads this file. Making it data-driven means adding new exercises in Phase 3+ requires only a YAML edit, no code change.
- **Expected Results:** YAML file that fully describes how to count reps and detect form issues for each of the 4 exercises.
- **Verification:**
  - [ ] YAML parses without error via `yaml.safe_load()`
  - [ ] Each exercise entry has keys: `name`, `primary_joint_pair`, `up_angle`, `down_angle`, `form_checks`
  - [ ] At least 2 form checks per exercise (e.g., squat: knee alignment, depth)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(exercise): add exercise definitions YAML\n\nTask: #T18`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T17
- **Notes:** Squat primary joint: hip-knee-ankle angle. Push-up: elbow angle. Bicep curl: elbow angle. Lateral raise: shoulder abduction angle. Joint indices follow MediaPipe/YOLO 17-keypoint convention.

---

## T19: Exercise Service — Exercise Registry

- **Status:** `COMPLETE`
- **Description:** Implement `services/exercise/src/exercise/exercise_registry.py`. Loads and validates `exercises.yaml` at startup. Provides `get_exercise(name: str) -> ExerciseDefinition` and `list_exercises() -> list[str]`.
- **Why:** The rep counter and form analyzer look up exercise definitions at runtime. Centralizing this prevents hardcoded thresholds scattered through the code.
- **Expected Results:** `ExerciseRegistry` class. `registry.get_exercise("squat")` returns an `ExerciseDefinition` dataclass with all thresholds loaded from YAML.
- **Verification:**
  - [ ] Unit test: load registry, verify all 4 exercises are present
  - [ ] `get_exercise("unknown")` raises `KeyError` with a helpful message
  - [ ] Adding a new entry to the YAML is picked up without code changes
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(exercise): add exercise registry\n\nTask: #T19`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T18

---

## T20: Exercise Service — Keypoint Utilities

- **Status:** `COMPLETE`
- **Description:** Implement `services/exercise/src/exercise/keypoint_utils.py`. Functions: `compute_angle(a, b, c) -> float` (angle at joint `b` given 3 keypoint coordinates), `smooth_signal(values: deque, window=5) -> float` (median filter), `keypoints_to_joint_angles(keypoints, exercise_def) -> dict[str, float]`.
- **Why:** Rep counting and form analysis both need stable joint angle measurements. The smoothing prevents false rep counts from noise.
- **Expected Results:** Pure functions, no I/O. `compute_angle` returns degrees (0-180). `smooth_signal` returns median of the deque.
- **Verification:**
  - [ ] Unit test: `compute_angle((0,0), (1,0), (1,1))` returns 90.0
  - [ ] Unit test: `smooth_signal(deque([10, 90, 20, 30, 40]))` returns 30.0
  - [ ] All functions handle low-visibility keypoints gracefully (visibility < 0.5 → return `None`)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(exercise): add keypoint utility functions\n\nTask: #T20`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T17

---

## T21: Exercise Service — Rep Counter (State Machine)

- **Status:** `COMPLETE`
- **Description:** Implement `services/exercise/src/exercise/rep_counter.py`. Per-track state machine that transitions between `up` and `down` phases based on primary joint angle crossing thresholds. Increments `rep_count` on each complete `down → up` cycle. Emits a `RepCountedEvent` on each completed rep.
- **Why:** Rep counting is the core metric the mobile app displays. It drives set tracking and progress statistics.
- **Expected Results:** `RepCounter(exercise_def: ExerciseDefinition)` class. `update(track_id, angle) -> RepCountedEvent | None`. Handles multiple simultaneous tracks (one counter instance per track stored in a dict).
- **Verification:**
  - [ ] Unit test: feed 10 simulated squat angle cycles → `rep_count` == 10
  - [ ] Unit test: noisy signal (random jitter around threshold) does not produce spurious counts
  - [ ] State resets correctly when a new set begins (track reappears after > 60s gap)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(exercise): add rep counter state machine\n\nTask: #T21`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T19, T20

---

## T22: Exercise Service — Form Analyzer

- **Status:** `COMPLETE`
- **Description:** Implement `services/exercise/src/exercise/form_analyzer.py`. On each frame, checks all `form_checks` from the exercise definition against current joint angles. If a joint angle is outside `[min_angle, max_angle]` for 3+ consecutive frames, emit a `FormAlertEvent` with the alert message.
- **Why:** Form alerts are the primary trigger for LLM guidance messages. They must be debounced (3 frames) to avoid flooding the guidance service.
- **Expected Results:** `FormAnalyzer(exercise_def: ExerciseDefinition)`. `check(track_id, joint_angles: dict) -> list[FormAlertEvent]`. Alerts are debounced: same alert not re-emitted within 10 seconds for the same track.
- **Verification:**
  - [ ] Unit test: angle outside threshold for 3 frames → 1 alert emitted
  - [ ] Unit test: angle outside threshold for 2 frames → 0 alerts
  - [ ] Unit test: same alert not re-emitted within 10s cooldown window
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(exercise): add form analyzer with debounce\n\nTask: #T22`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T19, T20

---

## T23: Exercise Service — Heuristic Exercise Classifier

- **Status:** `COMPLETE`
- **Description:** Implement `services/exercise/src/exercise/classifier.py` (Phase 1 heuristic version). Infers exercise type by measuring which joint angle shows the most variance over the last 30 frames. Returns `(exercise_name: str, confidence: float)`. Will be replaced by ONNX TCN in Phase 3.
- **Why:** Needed to automatically assign the correct `ExerciseDefinition` to a track without requiring manual input. Heuristic is good enough for Phase 1 prototype.
- **Expected Results:** `HeuristicClassifier`. `classify(pose_window: list[dict]) -> tuple[str, float]`. If no dominant joint activity detected, returns `("unknown", 0.0)`.
- **Verification:**
  - [ ] Unit test: 30 frames of simulated squat angles → returns `("squat", confidence > 0.6)`
  - [ ] Unit test: 30 frames of simulated bicep curl angles → returns `("bicep_curl", confidence > 0.6)`
  - [ ] Returns `"unknown"` for standing still (low variance across all joints)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(exercise): add heuristic exercise classifier\n\nTask: #T23`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T19, T20

---

## T24: Exercise Service — Integration (Consume Stream, Persist, Publish)

- **Status:** `COMPLETE`
- **Description:** Wire up `services/exercise/src/exercise/main.py`. Consumes `perceptions:{camera_id}` Redis Stream, runs Classifier → RepCounter → FormAnalyzer per tracked person per frame. Persists `ExerciseSet` and `RepEvent` rows to TimescaleDB. Publishes `rep_counted` and `form_alerts` events to Redis Streams.
- **Why:** This is the integration point that turns raw pose data into structured workout events consumed by the guidance service and stored for the mobile app's stats tab.
- **Expected Results:** With ingestion + perception running against a test video, `exercise_sets` and `rep_events` rows appear in the DB. `form_alerts` stream receives events when bad form is simulated.
- **Verification:**
  - [ ] Integration test: run full pipeline with a test video of squats → `rep_events` table has correct rep count
  - [ ] `redis-cli XRANGE form_alerts - + COUNT 1` returns a valid `FormAlertEvent` when bad form is present
  - [ ] `exercise_sets.rep_count` in DB matches actual reps in test video (±1)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(exercise): wire up full pipeline — consume, persist, publish\n\nTask: #T24`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T21, T22, T23, T04, T06, T16

---

## T25: Guidance Service — Scaffold (pyproject.toml, Dockerfile, Config)

- **Status:** `COMPLETE`
- **Description:** Create `services/guidance/` scaffold: `pyproject.toml` (depends on `gym_shared`, `anthropic`), `Dockerfile` (CPU, Python 3.11 slim), `src/guidance/config.py` (includes `ANTHROPIC_API_KEY`, rate limit settings), `src/guidance/main.py` stub.
- **Why:** Scaffold must exist before implementing LLM client and alert handler.
- **Expected Results:** `docker compose build guidance` succeeds.
- **Verification:**
  - [ ] `docker compose build guidance` exits 0
  - [ ] `import anthropic` succeeds inside the container
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `chore(guidance): add service scaffold\n\nTask: #T25`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T01, T02, T05

---

## T26: Guidance Service — LLM Client (Anthropic SDK Wrapper)

- **Status:** `COMPLETE`
- **Description:** Implement `services/guidance/src/guidance/llm_client.py`. `GymLLMClient` class wrapping `AsyncAnthropic`. Method `generate_guidance(system_prompt, messages, tools=None) -> str`. Handles API errors gracefully (log + return `None` on failure, do not crash the service).
- **Why:** All LLM calls route through this client. Centralizing error handling and model config here prevents duplication.
- **Expected Results:** `GymLLMClient` using model `claude-sonnet-4-6`. Async. Returns the text content of the first response block.
- **Verification:**
  - [ ] Integration test (requires `ANTHROPIC_API_KEY`): call with a simple prompt, verify non-empty string returned
  - [ ] On API error (mock 500), method returns `None` and logs the error, does not raise
  - [ ] `max_tokens=1024` by default, configurable via `config.py`
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(guidance): add Anthropic LLM client wrapper\n\nTask: #T26`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T25

---

## T27: Guidance Service — Form Alert Handler

- **Status:** `COMPLETE`
- **Description:** Implement `services/guidance/src/guidance/form_alert_handler.py`. Subscribes to `form_alerts` Redis Stream. For each alert: builds a short system prompt (exercise name, rep count, form issue), calls `GymLLMClient.generate_guidance()`, passes the result to `NotificationDispatcher`. Rate-limit: max 1 guidance message per 30 seconds per `track_id`.
- **Why:** This is the critical path for real-time coaching. Form alert → LLM → audio on user's headphones.
- **Expected Results:** `FormAlertHandler` async consumer. Processes form alerts, generates 1–2 sentence guidance, dispatches within ~2–3 seconds of the alert.
- **Verification:**
  - [ ] Integration test: publish a fake `FormAlertEvent`, verify a guidance message is dispatched within 5s
  - [ ] Rate limit test: publish 5 alerts for same track within 30s → only 1 LLM call made
  - [ ] System prompt includes exercise name and rep count from the alert
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(guidance): add form alert handler with rate limiting\n\nTask: #T27`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T26, T28, T06

---

## T28: Guidance Service — Notification Dispatcher

- **Status:** `COMPLETE`
- **Description:** Implement `services/guidance/src/guidance/notification_dispatcher.py`. `dispatch(track_id, message)` — looks up the active WebSocket session for the track in Redis (`track:{track_id}:ws_session`), sends the guidance message over the WebSocket. Logs to `notifications` DB table. If no active WS session, logs and drops (Phase 1; Phase 2 adds push notifications).
- **Why:** Delivers guidance to the user's phone/headphones. The WebSocket → TTS chain on the mobile app depends on this.
- **Expected Results:** `NotificationDispatcher`. Sends message to the correct WS session. Inserts a row into `notifications` table.
- **Verification:**
  - [ ] Unit test: mock WS session in Redis, call `dispatch`, verify message forwarded to correct session
  - [ ] `notifications` table row inserted with correct `track_id`, `content`, `sent_at`
  - [ ] No crash when `track_id` has no active WS session (logs "no active session" at INFO level)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(guidance): add notification dispatcher\n\nTask: #T28`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T25, T04

---

## T29: API Service — Scaffold + FastAPI App Factory


- **Status:** `COMPLETE`
- **Description:** Create `services/api/` scaffold: `pyproject.toml` (depends on `gym_shared`, `fastapi`, `uvicorn[standard]`, `python-jose`), `Dockerfile`, `src/api/main.py` (FastAPI app factory with lifespan, CORS, middleware), `src/api/dependencies.py` (DB session, Redis), `src/api/auth.py` (placeholder JWT middleware — accepts any token in Phase 1).
- **Why:** The mobile app and WebSocket clients connect to this service. Must exist as a runnable service before implementing endpoints.
- **Expected Results:** `docker compose up api` starts and `GET /healthz` returns `{"status": "ok"}`.
- **Verification:**
  - [ ] `curl http://localhost:8000/healthz` returns `{"status": "ok"}` with HTTP 200
  - [ ] OpenAPI docs available at `http://localhost:8000/docs`
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `chore(api): add FastAPI service scaffold\n\nTask: #T29`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T01, T02, T05

---

## T30: API Service — REST Endpoints (Sessions, Tracks, Replay)

- **Status:** `COMPLETE`
- **Description:** Implement REST routers in `services/api/src/api/routers/`: `sessions.py` (`GET /sessions/{session_id}`), `tracks.py` (`GET /tracks/{track_id}/history`, `GET /tracks/{track_id}/replay`). Schemas in `src/api/schemas/`.
- **Why:** The mobile app's Stats tab and Replay tab fetch data from these endpoints.
- **Expected Results:** All 3 endpoints return correct data from the DB. `/replay` returns a list of presigned MinIO URLs for video clips.
- **Verification:**
  - [ ] `GET /sessions/{id}` returns 404 for unknown ID, 200 with session data for a seeded session
  - [ ] `GET /tracks/{id}/history` returns list of `ExerciseSet` summaries
  - [ ] `GET /tracks/{id}/replay` returns list of presigned MinIO URLs (test with a manually seeded clip)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(api): add sessions, tracks history, and replay endpoints\n\nTask: #T30`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T29, T04

---

## T31: API Service — WebSocket Endpoint (/ws/live/{track_id})

- **Status:** `COMPLETE`
- **Description:** Implement `services/api/src/api/routers/websocket.py`. `WS /ws/live/{track_id}` — registers the connection in `WebSocketManager`, stores `track:{track_id}:ws_session` in Redis, streams `rep_counted`, `form_alert`, and `guidance` events to the client in real time.
- **Why:** The mobile app's Live Coaching tab connects here to receive real-time rep counts and audio guidance text.
- **Expected Results:** WebSocket connection for a `track_id` receives live events as JSON: `{"type": "rep_counted", "data": {...}}`, `{"type": "form_alert", ...}`, `{"type": "guidance", "data": {"text": "..."}}`.
- **Verification:**
  - [ ] `wscat -c ws://localhost:8000/ws/live/test-track` connects successfully
  - [ ] Publishing a fake `RepCountedEvent` to Redis → event appears on the WS client within 500ms
  - [ ] Disconnecting the WS client removes the session from Redis
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(api): add WebSocket live endpoint\n\nTask: #T31`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T29, T32

---

## T32: API Service — WebSocket Manager

- **Status:** `COMPLETE`
- **Description:** Implement `services/api/src/api/websocket_manager.py`. `WebSocketManager` maintains a registry of active connections keyed by `track_id`. Methods: `connect(track_id, ws)`, `disconnect(track_id)`, `send(track_id, message)`. Also runs a background task that subscribes to Redis Streams (`rep_counted`, `form_alerts`, `guidance`) and fans out messages to the correct WebSocket connections.
- **Why:** Decouples event routing logic from the WebSocket endpoint handler.
- **Expected Results:** Thread-safe manager. Multiple simultaneous connections for different `track_id`s all receive their respective events correctly.
- **Verification:**
  - [ ] Unit test: two WS connections for different track IDs, publish event for track A → only track A receives it
  - [ ] On `disconnect`, Redis session key is cleaned up
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(api): add WebSocket connection manager\n\nTask: #T32`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T29

---

## T33: API Service — Placeholder JWT Auth Middleware

- **Status:** `COMPLETE`
- **Description:** Implement `services/api/src/api/auth.py`. Phase 1 placeholder: any non-empty Bearer token is accepted (the token value is used as the `track_id`). Log a warning that real auth is not yet implemented. This will be replaced with proper JWT validation in Phase 2.
- **Why:** The mobile app QR code scan returns a `track_id`-based token. The API must accept it to associate the WS session with the correct track.
- **Expected Results:** `get_current_track_id(token: str = Depends(oauth2_scheme)) -> str` FastAPI dependency. Returns the token string as the track ID.
- **Verification:**
  - [ ] `curl -H "Authorization: Bearer cam-01-track-5" http://localhost:8000/tracks/cam-01-track-5/history` succeeds (200 or 404, not 401)
  - [ ] Missing `Authorization` header returns 401
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(api): add placeholder JWT auth middleware\n\nTask: #T33`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T29

---

## T34: Mobile App — React Native Project Init (iOS)

- **Status:** `COMPLETE`
- **Description:** Initialize the React Native project in `mobile/` using `react-native init SmartGym --template react-native-template-typescript`. Set up: ESLint + Prettier, React Navigation (bottom tabs), basic tab structure (Live Coaching, Replay, Stats). iOS build must succeed.
- **Why:** All mobile tasks depend on the project existing and building.
- **Expected Results:** `npx react-native run-ios` opens the app in the simulator with 3 bottom tabs (placeholder screens).
- **Verification:**
  - [ ] `npx react-native run-ios` succeeds with no build errors
  - [ ] 3 bottom tabs visible: "Live Coaching", "Replay", "Stats"
  - [ ] TypeScript compiles with `tsc --noEmit`
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `chore(mobile): init React Native project with tab navigation\n\nTask: #T34`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** None (independent of backend tasks)
- **Notes:** Min iOS target: 15.0. Use React Navigation v6. Install: `@react-navigation/native`, `@react-navigation/bottom-tabs`, `react-native-screens`, `react-native-safe-area-context`.

---

## T35: Mobile App — QR Code Scan Screen (Session Token)

- **Status:** `COMPLETE`
- **Description:** Implement the QR code scan screen. When the user opens the app, they see a "Start Session" button that opens the camera to scan a QR code. The QR code encodes a `track_id` (printed at the gym entrance or shown on a kiosk). On successful scan, the `track_id` is stored in app state and used as the auth token for all API calls.
- **Why:** This is how users link their phone to their anonymous track in Phase 1. Required before the Live Coaching and Stats tabs can show personalized data.
- **Expected Results:** QR scan screen using `react-native-vision-camera` + `vision-camera-code-scanner`. On scan, navigates to the main tab view with the track_id set.
- **Verification:**
  - [ ] Scanning a QR code containing `"track-123"` stores `track_id = "track-123"` in state
  - [ ] Invalid QR (non-track payload) shows an error toast, does not navigate
  - [ ] Session persists across app restarts (`AsyncStorage`)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(mobile): add QR code scan session start screen\n\nTask: #T35`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T34, T33

---

## T36: Mobile App — Live Coaching Tab (WebSocket + TTS)

- **Status:** `COMPLETE`
- **Description:** Implement the Live Coaching tab. Connects to `WS /ws/live/{track_id}`. Displays current exercise name and rep count (updated live). On receiving a `guidance` event, reads the text aloud using React Native's `react-native-tts` (native TTS → headphone output). Shows a scrollable log of recent guidance messages.
- **Why:** This is the primary Phase 1 user experience. Users hear coaching through their headphones while exercising.
- **Expected Results:** Live rep count increments in real time. Guidance text is spoken via TTS immediately on receipt. Works with AirPods / wired headphones.
- **Verification:**
  - [ ] With backend running, rep count on screen matches `rep_events` being inserted in DB
  - [ ] Publishing a test `guidance` event triggers TTS speech on the device
  - [ ] WS reconnects automatically after a 5s disconnection
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(mobile): add live coaching tab with WebSocket and TTS\n\nTask: #T36`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T34, T31

---

## T37: Mobile App — Movement Replay Tab

- **Status:** `COMPLETE`
- **Description:** Implement the Movement Replay tab. Fetches `GET /tracks/{track_id}/replay` to get a list of video clip URLs. Displays clips in a scrollable list with timestamp and exercise label. Each clip is playable inline using `react-native-video`.
- **Why:** Users want to review their movement form after the session. This is the main differentiator over a simple rep counter.
- **Expected Results:** List of video clips, each with a play button. Tapping plays the H.264 clip inline. List shows the exercise name and timestamp for each clip.
- **Verification:**
  - [ ] Clips fetched from the API are listed with correct labels
  - [ ] Tapping a clip plays it inline without leaving the tab
  - [ ] Empty state shown when no clips are available yet
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(mobile): add movement replay tab\n\nTask: #T37`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T34, T30

---

## T38: Mobile App — Stats Tab

- **Status:** `COMPLETE`
- **Description:** Implement the Stats tab. Fetches `GET /sessions/{session_id}` (current session) and `GET /tracks/{track_id}/history`. Displays: total session time, list of exercise sets with rep counts, form score per set (0–100%).
- **Why:** Users want a summary of what they did. Drives motivation and progress tracking.
- **Expected Results:** Session summary card at top (duration, total reps). Below: list of sets grouped by exercise with rep count and form score badge.
- **Verification:**
  - [ ] Stats update when navigating to the tab after completing sets
  - [ ] Form score displayed as a colored badge (green >80%, yellow 50–80%, red <50%)
  - [ ] Empty state shown for a fresh session with no sets yet
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(mobile): add stats tab\n\nTask: #T38`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T34, T30

---

## T39: Worker Service — Scaffold (Celery + pyproject.toml + Dockerfile)

- **Status:** `COMPLETE`
- **Description:** Create `services/worker/` scaffold: `pyproject.toml` (depends on `gym_shared`, `celery[redis]`, `av`, `minio`), `Dockerfile` (CPU, Python 3.11 slim), `src/worker/app.py` (Celery app configured with Redis broker/backend), `src/worker/config.py`.
- **Why:** The video clip save task runs asynchronously so it doesn't block the form alert handler.
- **Expected Results:** `docker compose up worker` starts the Celery worker and logs "celery@worker ready".
- **Verification:**
  - [ ] `docker compose up worker` starts without error
  - [ ] `celery -A worker.app inspect ping` returns a pong
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `chore(worker): add Celery service scaffold\n\nTask: #T39`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T01, T02, T05

---

## T40: Worker Service — Video Clip Save Task

- **Status:** `COMPLETE`
- **Description:** Implement `services/worker/src/worker/tasks/video_clip.py`. Celery task `save_clip(camera_id, track_id, exercise_set_id, timestamp_ns)`. Retrieves the 5-second window of frames (225 frames at 15 FPS) from the ingestion service's rolling buffer (shared via Redis — ingestion stores frame buffer as a Redis list). Encodes to H.264 MP4 via `PyAV`. Uploads to MinIO bucket `gym-clips`. Updates `ExerciseSet.alerts` JSONB with the clip URL.
- **Why:** Video replay is a core Phase 1 mobile feature. Clips must be saved when form alerts fire.
- **Expected Results:** Task runs within 10 seconds of being queued. H.264 MP4 clip appears in MinIO. `exercise_sets` row updated with clip URL.
- **Verification:**
  - [ ] Manually queue the task with a test camera_id and timestamp → MP4 appears in MinIO `gym-clips` bucket
  - [ ] `exercise_sets.alerts` JSONB field contains `{"clip_url": "http://..."}`
  - [ ] Clip is playable (valid H.264 encoding)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(worker): add video clip save Celery task\n\nTask: #T40`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T39, T04
- **Notes:** Store rolling frame buffer in ingestion as a Redis list `buffer:{camera_id}` with `LPUSH` + `LTRIM` to cap at 225 entries. Each entry is the JPEG bytes. Worker reconstructs the video from this list.

---

## T41: Guidance Service — Trigger Video Clip on Form Alert

- **Status:** `COMPLETE`
- **Description:** Update `form_alert_handler.py` to also queue a `save_clip` Celery task whenever a `FormAlertEvent` is processed. Pass `camera_id`, `track_id`, `exercise_set_id`, and the alert timestamp.
- **Why:** Connects the form alert pipeline to the video clip worker, completing the loop from alert detection → clip saved → clip URL available in the mobile Replay tab.
- **Expected Results:** Every form alert triggers both an LLM guidance message and a Celery `save_clip` task. Within ~10s, the clip appears in MinIO.
- **Verification:**
  - [ ] Trigger a form alert in integration test → verify both guidance message dispatched AND clip saved to MinIO
  - [ ] `exercise_sets.alerts` updated with clip URL within 15s of the alert
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(guidance): trigger video clip save on form alert\n\nTask: #T41`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T40, T27

---

## Phase 1 — End-to-End Verification Checklist

- [ ] `make dev-up` starts all infrastructure containers healthy
- [ ] `python scripts/setup_db.py` runs migrations cleanly
- [ ] `python scripts/register_camera.py --id cam-01 --rtsp-url <url> --zone weights` creates camera row
- [ ] Start ingestion + perception + exercise + guidance + api + worker services
- [ ] Run a test video through the pipeline; `rep_events` table shows correct rep counts
- [ ] Trigger a form alert; LLM guidance text appears on a WS client within 5 seconds
- [ ] Video clip appears in MinIO within 15 seconds of a form alert
- [ ] Open mobile app, scan QR code, verify Live Coaching tab shows live rep count
- [ ] Speak guidance text plays through headphones
- [ ] Movement Replay tab shows video clips from the session
- [ ] Stats tab shows session duration, exercise sets, and form scores

---

# Phase 2 Tasks — Person Identification & Personalized Experience

> Phase 2 Goal: Link anonymous tracks to registered gym members. AI greets users by name, asks what they want to work on, recommends a personalized workout plan, provides coaching using their history and goals, and supports voice + text conversation mid-workout.

> **After completing every task:** run all verification checks → `git status` → `git add <files>` → commit with `feat(<scope>): <desc>\n\nTask: #[ID]` → `git push origin main` → update status to `COMPLETE` → append to `docs/progress.md`.

---

## T42: Shared Package — Phase 2 ORM Models

- **Status:** `COMPLETE`
- **Description:** Add Phase 2 SQLAlchemy 2.0 async ORM models to `shared/src/gym_shared/db/models.py`:
  - `Person` — registered gym member; fields: `id`, `name`, `face_embedding` (Vector 512), `reid_gallery` (array of Vector 256), `goals` (JSONB), `injury_notes` (text), `fcm_token`, `notification_prefs` (JSONB), `created_at`
  - `Conversation` — one LLM chat thread per person per session; fields: `id`, `person_id` (FK), `gym_session_id` (FK), `created_at`
  - `Message` — individual message in a conversation; fields: `id`, `conversation_id` (FK), `role` (enum: user/assistant), `content` (text), `created_at`
  - `GymKnowledge` — RAG document store; fields: `id`, `title`, `content`, `embedding` (Vector 384), `category`, `created_at`
  - Add `workout_plan` (JSONB, nullable) column to existing `GymSession` model
- **Why:** All Phase 2 services depend on these models. Must exist before migrations.
- **Expected Results:** All new models importable from `gym_shared.db.models`. Relationships defined (Conversation → Person, Message → Conversation, etc.).
- **Verification:**
  - [ ] `from gym_shared.db.models import Person, Conversation, Message, GymKnowledge` succeeds
  - [ ] `Person.face_embedding` uses `Vector(512)`, `GymKnowledge.embedding` uses `Vector(384)`
  - [ ] `GymSession` has `workout_plan` column
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` → commit: `feat(shared): add Phase 2 ORM models (Person, Conversation, Message, GymKnowledge)\n\nTask: #T42`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T04

---

## T43: Shared Package — Alembic Migration for Phase 2 Tables

- **Status:** `COMPLETE`
- **Description:** Write Alembic migration that: creates `persons`, `conversations`, `messages`, `gym_knowledge` tables; adds `workout_plan` JSONB column to `gym_sessions`; creates pgvector indexes (`ivfflat`) on `persons.face_embedding` and `gym_knowledge.embedding` for fast cosine similarity search.
- **Why:** DB schema must exist before any Phase 2 service can persist or query data.
- **Expected Results:** `make migrate` runs cleanly. All new tables exist. Vector indexes created.
- **Verification:**
  - [ ] `make migrate` exits 0 on a DB that has Phase 1 schema
  - [ ] `\d persons` in psql shows all columns including `face_embedding vector(512)`
  - [ ] `\d gym_knowledge` shows `embedding vector(384)`
  - [ ] `SELECT indexname FROM pg_indexes WHERE tablename = 'persons'` includes the ivfflat index
  - [ ] Re-running migration is idempotent
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(shared): add Phase 2 Alembic migration\n\nTask: #T43`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T42

---

## T44: Scripts — Person Registration CLI

- **Status:** `COMPLETE`
- **Description:** Implement `scripts/register_person.py`. CLI tool that:
  1. Accepts `--name`, `--goals` (comma-separated), `--injury-notes` (optional)
  2. Captures 5 face photos from a connected camera (or accepts `--photos-dir` with existing images)
  3. Extracts ArcFace 512-d face embedding via InsightFace
  4. Prompts the person to walk in front of each registered camera to seed 10-frame OSNet ReID gallery
  5. Inserts `Person` record into DB
  6. Generates and saves a QR code PNG (`output/person_{id}_qr.png`) encoding the person's `track_id` for fallback login
- **Why:** Required to register gym members so they can be identified by the system.
- **Expected Results:** Running the script creates a `Person` row with populated face embedding and ReID gallery. QR code PNG generated.
- **Verification:**
  - [ ] `python scripts/register_person.py --name "Test User" --goals "strength,weight_loss"` creates a DB row
  - [ ] `SELECT face_embedding IS NOT NULL FROM persons WHERE name = 'Test User'` returns true
  - [ ] QR code PNG file is created and scannable
  - [ ] Running twice with same name creates a second person (not an upsert)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(scripts): add person registration CLI\n\nTask: #T44`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T43
- **Notes:** InsightFace: `pip install insightface onnxruntime`. Use `app = insightface.app.FaceAnalysis()`, `app.prepare(ctx_id=0)`. ArcFace embedding from `face.embedding` (512-d, L2-normalize before storing).

---

## T45: ReID Service — Scaffold (pyproject.toml, Dockerfile, Config)

- **Status:** `COMPLETE`
- **Description:** Create `services/reid/` service scaffold: `pyproject.toml` (depends on `gym_shared`, `insightface`, `torchreid`, `onnxruntime`, `pgvector`), `Dockerfile` (CPU, Python 3.11 slim), `src/reid/config.py` (similarity thresholds, gallery cache TTL), `src/reid/main.py` stub.
- **Why:** Scaffold must exist before implementing matching logic.
- **Expected Results:** `docker compose build reid` succeeds. Service starts and logs "ReID service starting".
- **Verification:**
  - [ ] `docker compose build reid` exits 0
  - [ ] `import insightface; import torchreid` succeeds inside the container
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `chore(reid): add service scaffold\n\nTask: #T45`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T01, T02, T05

---

## T46: ReID Service — Gallery Manager

- **Status:** `COMPLETE`
- **Description:** Implement `services/reid/src/reid/gallery_manager.py`. Methods:
  - `upsert_embedding(person_id, reid_embedding)` — adds embedding to `persons.reid_gallery` array in DB
  - `search_gallery(query_embedding) -> list[tuple[person_id, similarity]]` — pgvector cosine similarity search against all person embeddings, returns top-5 matches
  - `refresh_cache()` — loads all person embeddings into Redis hash `reid:gallery` for sub-ms in-memory matching
  - `get_from_cache(query_embedding) -> person_id | None` — cosine similarity against Redis cache, returns match if similarity > threshold (default 0.75)
- **Why:** Gallery lookups must be fast (< 50ms) to not delay identity resolution. Redis cache enables this.
- **Expected Results:** `GalleryManager` class. Cache refresh populates Redis. `search_gallery` returns correct person for a test embedding.
- **Verification:**
  - [ ] Unit test: insert a known embedding, search with identical embedding → similarity ≈ 1.0, correct person_id returned
  - [ ] Unit test: search with random embedding → no match above threshold
  - [ ] Redis cache populated after `refresh_cache()` — `redis-cli HLEN reid:gallery` > 0
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(reid): add gallery manager with pgvector and Redis cache\n\nTask: #T46`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T45, T43

---

## T47: ReID Service — Identity Matcher (OSNet + ArcFace Fusion)

- **Status:** `COMPLETE`
- **Description:** Implement `services/reid/src/reid/matcher.py`. `IdentityMatcher` class:
  - Maintains a per-track embedding buffer (last 10 OSNet embeddings, averaged)
  - `update(track_id, reid_embedding, face_crop=None) -> person_id | None`
    - Averages last 10 embeddings for the track
    - Queries gallery cache; if cosine similarity > 0.75 → candidate match
    - If face crop provided + ArcFace similarity > 0.85 → ground-truth override (higher confidence)
    - Applies spatial-temporal gating: boost score if track appears near a camera boundary within 10s of another track exiting
  - `clear_track(track_id)` — removes track buffer on track loss
- **Why:** This is the core identity resolution logic. Fusing appearance (OSNet) and face (ArcFace) maximizes accuracy in a gym environment where clothing is similar.
- **Expected Results:** `IdentityMatcher` correctly identifies a registered person from their ReID embeddings with >80% accuracy on test data.
- **Verification:**
  - [ ] Unit test: 10 embeddings from a registered person → correct `person_id` returned
  - [ ] Unit test: unknown person embeddings → returns `None`
  - [ ] Face crop override: low OSNet similarity + high ArcFace similarity → still resolves correctly
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(reid): add OSNet+ArcFace identity matcher\n\nTask: #T47`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T46

---

## T48: ReID Service — Identity Resolver (Stream Consumer + Publisher)

- **Status:** `COMPLETE`
- **Description:** Wire up `services/reid/src/reid/main.py`. Consumes `perceptions:{camera_id}` Redis Stream. For each perception event:
  1. Passes `reid_embedding` (and face crop if visible) to `IdentityMatcher`
  2. When identity resolved: updates `Track.global_person_id` in DB, publishes `identity_resolved` event to `identity_resolved:{camera_id}` Redis Stream
  3. Triggers session onboarding if this is a new session for the person (no active `GymSession` in last 4 hours)
- **Why:** This service closes the loop between anonymous CV tracking and registered person identity.
- **Expected Results:** With a registered person in front of the camera, `tracks.global_person_id` is populated within ~10 seconds. `identity_resolved` events appear in Redis.
- **Verification:**
  - [ ] Integration test: register a person, run pipeline → `tracks.global_person_id` populated
  - [ ] `redis-cli XRANGE identity_resolved:cam-01 - + COUNT 1` returns a valid event with `person_id`
  - [ ] Unknown person does not populate `global_person_id` (remains NULL)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(reid): wire up identity resolver stream consumer\n\nTask: #T48`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T47, T06

---

## T49: Guidance Service — Personalized Prompt Builder

- **Status:** `COMPLETE`
- **Description:** Implement `services/guidance/src/guidance/prompt_builder.py`. `PromptBuilder` class:
  - `build_system_prompt(person_id) -> str` — fetches person's name, goals, injury notes, last 5 sessions summary from DB; constructs a rich system prompt personalizing the AI trainer persona
  - `build_form_alert_prompt(person, exercise, rep_count, alert_message) -> str` — personalized form correction prompt using person's name and history
  - `build_onboarding_prompt(person) -> str` — session start prompt: greet by name, reference last workout, ask what they want to focus on today
- **Why:** Personalized prompts are what differentiate Phase 2 from Phase 1's generic guidance.
- **Expected Results:** `PromptBuilder` produces prompts that include the person's name, recent history, and goals. Verified by inspecting prompt strings in unit tests.
- **Verification:**
  - [ ] Unit test: `build_system_prompt(person_id)` output contains person's name and at least one goal
  - [ ] Unit test: `build_onboarding_prompt` output references the last session date
  - [ ] No DB call made if person has no history (graceful fallback to generic prompt)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(guidance): add personalized prompt builder\n\nTask: #T49`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T43, T26

---

## T50: Guidance Service — LLM Tool Definitions + Executor

- **Status:** `COMPLETE`
- **Description:** Implement `services/guidance/src/guidance/tool_definitions.py` and `tool_executor.py`. Tools:
  - `get_workout_history(person_id, days=7)` — returns list of sessions with exercises, reps, form scores
  - `get_exercise_stats(person_id, exercise_name)` — returns personal bests, average form score, trend
  - `suggest_workout_plan(person_id, focus_area, duration_minutes)` — generates a structured workout plan using history + LLM knowledge
  - `get_person_profile(person_id)` — returns goals, injury notes, experience level
- **Why:** LLM tools allow the AI to query real user data when answering questions or building recommendations, rather than hallucinating.
- **Expected Results:** Tools defined in Anthropic tool-use format. `ToolExecutor.run(tool_name, tool_input) -> str` dispatches to correct DB query and returns JSON string result.
- **Verification:**
  - [ ] Unit test: `get_workout_history` with seeded DB data returns correct sessions
  - [ ] Unit test: `suggest_workout_plan` returns a structured plan dict
  - [ ] Unknown tool name raises `ValueError` with helpful message
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(guidance): add LLM tool definitions and executor\n\nTask: #T50`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T49

---

## T51: Guidance Service — Session Onboarding Conversation

- **Status:** `COMPLETE`
- **Description:** Implement `services/guidance/src/guidance/session_onboarding.py`. `SessionOnboardingHandler`:
  - Triggered by `identity_resolved` events from Redis Stream (new session detected)
  - Calls `PromptBuilder.build_onboarding_prompt(person)` to greet user and ask about today's goals
  - Delivers greeting via WebSocket (→ TTS on mobile) within 3 seconds of identity resolution
  - Maintains a short back-and-forth conversation (up to 3 turns) to clarify the workout plan
  - Calls `suggest_workout_plan` tool based on user's response
  - Stores the accepted plan in `GymSession.workout_plan` JSONB field
  - Publishes `onboarding_complete` event to Redis when plan is accepted
- **Why:** This is the key Phase 2 feature — the AI proactively engages with the user at session start to set the workout context.
- **Expected Results:** When a registered person is identified, they receive a personalized greeting within 3 seconds. After 1–3 exchanges, a workout plan is agreed upon and stored.
- **Verification:**
  - [ ] Integration test: trigger `identity_resolved` event → guidance message dispatched within 3s
  - [ ] Simulated user response → AI returns a workout plan
  - [ ] `gym_sessions.workout_plan` populated after onboarding completes
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(guidance): add session onboarding conversation handler\n\nTask: #T51`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T50, T48

---

## T52: Guidance Service — Conversation Manager (Full Chat + RAG)

- **Status:** `COMPLETE`
- **Description:** Implement `services/guidance/src/guidance/conversation_manager.py`. `ConversationManager`:
  - `send_message(conversation_id, person_id, user_text) -> str` — adds user message to `messages` table, builds context (last 20 messages from Redis, older ones summarized), queries RAG (`GymKnowledge` pgvector search, top-3 chunks injected into system prompt), calls LLM with tools, persists assistant reply, returns text
  - Context window management: keep last 20 messages in Redis `conv:{conversation_id}:messages`; when count exceeds 20, summarize oldest 10 via LLM and replace with summary
  - Personal best detection: after each set completion, check if it's a PB; if so, trigger a motivational message
- **Why:** Enables ongoing mid-workout conversation and follow-up questions beyond the onboarding flow.
- **Expected Results:** Full conversation roundtrip works end-to-end. RAG context is injected when relevant knowledge exists. Context window stays bounded.
- **Verification:**
  - [ ] Integration test: send 3 messages, verify all persisted in DB and Redis
  - [ ] RAG test: seed a `GymKnowledge` entry about squats, ask about squat form → knowledge chunk appears in LLM context
  - [ ] Context overflow: send 25 messages → oldest 10 get summarized, Redis list stays at ≤20 entries
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(guidance): add conversation manager with RAG and context management\n\nTask: #T52`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T50

---

## T53: API Service — Conversation Endpoints + JWT Auth Upgrade

- **Status:** `COMPLETE`
- **Description:** Two parts:
  1. Add conversation endpoints to `services/api/src/api/routers/conversations.py`:
     - `POST /conversations` — create a new conversation for the current person+session
     - `POST /conversations/{conversation_id}/messages` — send a user message, get AI response
     - `GET /conversations/{conversation_id}/messages` — fetch message history
  2. Upgrade `auth.py` from placeholder (token = track_id) to proper JWT: issue a signed JWT on QR scan containing `person_id` + `track_id`; validate signature on all requests. Use `python-jose`.
- **Why:** The mobile chat screen needs these endpoints. Proper auth is required before Phase 2 goes to any real users.
- **Expected Results:** Conversation CRUD works. JWT tokens are signed and validated. Existing Phase 1 endpoints still work.
- **Verification:**
  - [ ] `POST /conversations/{id}/messages` with a user message returns AI response within 5s
  - [ ] `GET /conversations/{id}/messages` returns message history in correct order
  - [ ] Invalid/expired JWT returns 401
  - [ ] Phase 1 endpoints (`/sessions`, `/tracks`, `/ws/live`) still return correct responses
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(api): add conversation endpoints and proper JWT auth\n\nTask: #T53`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T52, T33

---

## T54: Mobile App — Speech-to-Text (Voice Input)

- **Status:** `IN_QUEUE`
- **Description:** Add voice input capability to the mobile app. Implement `mobile/src/hooks/useSpeechToText.ts` using `@react-native-voice/voice`. Hook exposes: `startListening()`, `stopListening()`, `transcript: string`, `isListening: boolean`. Integrate into a reusable `VoiceInputButton` component that shows a microphone icon, glows while recording, and returns the transcript on stop.
- **Why:** Users need to be able to speak to the AI during workouts without typing. Core requirement for Phase 2 conversational interface.
- **Expected Results:** `VoiceInputButton` records speech and returns transcript. Works on iOS with microphone permission.
- **Verification:**
  - [ ] Tapping mic button starts recording; tapping again stops and returns transcript
  - [ ] Microphone permission prompt shown on first use
  - [ ] Transcript accuracy: simple sentences ("I want to work on legs today") captured correctly
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(mobile): add speech-to-text voice input hook and component\n\nTask: #T54`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T34
- **Notes:** Install: `npm install @react-native-voice/voice` + `pod install`. iOS requires `NSMicrophoneUsageDescription` and `NSSpeechRecognitionUsageDescription` in `Info.plist`.

---

## T55: Mobile App — Session Onboarding + Workout Plan Screen

- **Status:** `IN_QUEUE`
- **Description:** Implement `mobile/src/screens/OnboardingScreen.tsx`. Shown automatically when a `guidance` WebSocket event of type `onboarding` is received. Displays:
  - AI greeting message (also spoken via TTS)
  - Voice input button for user response (uses `VoiceInputButton` from T54)
  - After plan is generated: a card showing today's recommended workout (exercise list, sets, reps)
  - "Let's go" button to accept + dismiss, or "Change it" to ask for an alternative (sends another voice message)
  - Accepted plan stored locally and displayed as a checklist in the Live Coaching tab
- **Why:** The onboarding conversation is the signature Phase 2 UX. Must be visually clear and voice-first.
- **Expected Results:** Onboarding screen appears on session start, accepts voice response, displays recommended plan, dismisses on accept.
- **Verification:**
  - [ ] Screen appears when `onboarding` WS event received
  - [ ] Voice input captured and sent to `POST /conversations/{id}/messages`
  - [ ] Workout plan card renders with correct exercise list from API response
  - [ ] "Let's go" dismisses screen and shows plan checklist in Live tab
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(mobile): add session onboarding and workout plan screen\n\nTask: #T55`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T54, T53, T51

---

## T56: Mobile App — Chat Screen (Voice + Text Mid-Workout)

- **Status:** `IN_QUEUE`
- **Description:** Implement `mobile/src/screens/ChatScreen.tsx` as a 4th tab ("Coach"). Provides a full conversational interface:
  - Scrollable message history (user messages right-aligned, AI messages left-aligned)
  - Text input field + send button for typed messages
  - `VoiceInputButton` for voice input (transcript auto-fills text input before send)
  - AI responses displayed as text and spoken via TTS
  - Loading indicator while waiting for AI response
- **Why:** Users need to ask questions mid-workout ("how many more sets should I do?", "what's good for sore shoulders?").
- **Expected Results:** Full chat UI working end-to-end. Voice and text input both work. Responses displayed and spoken.
- **Verification:**
  - [ ] Typed message sent → AI response appears within 5s and is spoken via TTS
  - [ ] Voice message: tap mic → speak → transcript fills input → send → response received
  - [ ] Message history scrolls correctly with many messages
  - [ ] Loading spinner shown during API call
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(mobile): add chat screen with voice and text input\n\nTask: #T56`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T54, T53

---

## T57: Mobile App — Profile Screen

- **Status:** `IN_QUEUE`
- **Description:** Implement `mobile/src/screens/ProfileScreen.tsx` as a 5th tab ("Profile"). Displays and allows editing of:
  - Name
  - Goals (multi-select: strength, weight loss, endurance, flexibility, muscle gain)
  - Injury notes (free text)
  - Notification preferences (form alerts on/off, guidance frequency: always/sometimes/never)
  - "Sign out" button (clears stored track_id + JWT)
- **Why:** Users need to set their goals and injury context so the AI can personalize guidance correctly.
- **Expected Results:** Profile screen loads current data from `GET /persons/{person_id}`. Edits saved via `PATCH /persons/{person_id}`. Changes reflected in next LLM prompt immediately.
- **Verification:**
  - [ ] Profile data loads on screen open
  - [ ] Saving a goal change updates the DB (verify via `SELECT goals FROM persons`)
  - [ ] Sign out clears session and returns to QR scan screen
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(mobile): add profile screen\n\nTask: #T57`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T53

---

## T58: Mobile App — Workout History Screen

- **Status:** `IN_QUEUE`
- **Description:** Implement `mobile/src/screens/HistoryScreen.tsx`. Displays:
  - Calendar heatmap (last 90 days, color intensity = total reps that day) using `react-native-calendars`
  - Tapping a day shows that day's sessions
  - Each session: expandable card with exercises, sets, rep counts, form score badge
  - "Personal bests" section at top: best rep count per exercise
- **Why:** Workout history motivates users and provides context for the AI's workout recommendations.
- **Expected Results:** History screen loads and displays past sessions from `GET /tracks/{track_id}/history`. Calendar correctly shades active days.
- **Verification:**
  - [ ] Calendar shows correct shading for days with workout data
  - [ ] Tapping a day expands to show session details
  - [ ] Personal bests section shows correct max rep counts per exercise
  - [ ] Empty state shown for new users with no history
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(mobile): add workout history screen with calendar heatmap\n\nTask: #T58`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T53

---

## T59: Scripts — Seed Gym Knowledge Base (RAG)

- **Status:** `IN_QUEUE`
- **Description:** Implement `scripts/seed_gym_knowledge.py`. Loads a set of exercise guides (proper form, common mistakes, variations for squat, push-up, bicep curl, lateral raise, deadlift, bench press), safety guidelines, and basic recovery/nutrition notes. For each document: generate a 384-d sentence-transformers embedding and insert into `gym_knowledge` table.
- **Why:** The RAG retriever needs content to inject into LLM prompts. Without seeded knowledge, the AI has no gym-specific reference material.
- **Expected Results:** `gym_knowledge` table populated with ≥20 entries. pgvector similarity search returns relevant entries for exercise-related queries.
- **Verification:**
  - [ ] Script runs without error and inserts ≥20 rows
  - [ ] `SELECT COUNT(*) FROM gym_knowledge` ≥ 20
  - [ ] Similarity search for "knee cave squat" returns a squat form entry (cosine similarity > 0.7)
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] `git add <specific files>` → commit: `feat(scripts): seed gym knowledge base for RAG\n\nTask: #T59`
  - [ ] `git push origin main`
  - [ ] Set status to `COMPLETE`, append entry to `docs/progress.md`
- **Dependencies:** T43
- **Notes:** Use `sentence-transformers` model `all-MiniLM-L6-v2` (384-d). Store content as plain text chunks of ~200 words. Include source/category tag (e.g., `"exercise_form"`, `"safety"`, `"nutrition"`).

---

## Phase 2 — End-to-End Verification Checklist

- [ ] `python scripts/register_person.py --name "Test User" --goals "strength"` creates person + QR code
- [ ] Start all services including new `reid` service
- [ ] Walk in front of camera — within 10s `tracks.global_person_id` is populated
- [ ] AI greeting appears on mobile app within 3s of identity resolution, spoken via TTS
- [ ] Respond via voice — AI generates and displays a workout plan
- [ ] Accept plan — `gym_sessions.workout_plan` populated, plan checklist shown in Live tab
- [ ] Trigger a form alert — guidance message uses person's name and references their goals
- [ ] Open Chat tab, ask "how many sets should I do today?" — AI responds using workout history
- [ ] Voice input: tap mic, speak a question — transcript captured, AI responds via TTS
- [ ] Profile screen: update a goal, verify next LLM response reflects the change
- [ ] History screen: past sessions visible with correct rep counts and form scores
