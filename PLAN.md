# Smart Gym System — Concrete Implementation Plan

## Context

A gym wants to use a multi-camera computer vision system to automatically track every person exercising, recognize who each person is, and deliver real-time personalized coaching. Users can also converse with an AI trainer for workout planning and encouragement. The system must be designed for extensibility and rolled out in phases, with a hybrid (local GPU + cloud LLM) prototype as the starting point.

---

## System Overview

Seven loosely coupled services communicate via a message bus (Redis Streams in early phases, Kafka in Phase 4+). Each service is independently deployable and tested.

```
[Camera Network] → [Ingestion] → [Perception] → [ReID] → [Exercise Analysis]
                                                                    ↓
                                                          [Event Bus (Redis)]
                                                            ↙          ↘
                                                [LLM Guidance]    [Data Store]
                                                        ↓
                                                  [API Gateway]
                                                        ↓
                                                  [Mobile App]
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| CV/AI pipeline | Python 3.11, PyTorch, Ultralytics YOLOv11, MediaPipe |
| Intra-camera tracking | ByteTrack (built into Ultralytics) |
| Cross-camera ReID | OSNet (torchreid), pgvector cosine similarity |
| Face recognition | InsightFace (ArcFace) |
| Exercise classifier | ONNX-exported TCN (Temporal Conv Net on pose keypoints) |
| LLM | Claude claude-sonnet-4-6 via Anthropic SDK (cloud) |
| RAG embeddings | sentence-transformers + pgvector |
| API | FastAPI (async REST + WebSocket) |
| Message bus | Redis Streams → Kafka (Phase 4) |
| Database | PostgreSQL + TimescaleDB + pgvector |
| Live state cache | Redis |
| Object storage | MinIO (local) / S3 (cloud) |
| Mobile app | React Native |
| Infrastructure | Docker Compose → Kubernetes (Phase 4) |

---

## Proposed Directory Structure

```
smart-gym/
├── services/
│   ├── ingestion/          # RTSP stream reader → Redis Streams
│   ├── perception/         # YOLO detection + pose + ReID features
│   ├── reid/               # Cross-camera identity resolver
│   ├── exercise/           # Exercise classification, rep counting, form analysis
│   ├── guidance/           # LLM conversations, RAG, notification dispatch
│   ├── api/                # FastAPI REST + WebSocket gateway
│   └── worker/             # Celery tasks (video clips, push notifications)
├── shared/                 # Internal Python package (ORM models, events, settings)
│   └── src/gym_shared/
│       ├── db/             # SQLAlchemy models + Alembic migrations
│       ├── events/         # Redis Streams event schemas
│       └── utils/          # Geometry (homography), logging
├── ml/
│   ├── exercise_classifier/  # TCN training + ONNX export
│   ├── reid_finetuning/      # OSNet fine-tune on gym data
│   └── data_collection/      # Pose recording + annotation tools
├── scripts/                # DB setup, camera registration, person enrollment
├── infrastructure/         # Docker Compose, Nginx, Prometheus, Grafana, K8s
└── docs/                   # Architecture, ADRs, camera setup guide
```

---

## Core Data Models

### PostgreSQL Entities
- **Person** — registered gym member; stores ArcFace embedding (vector 512), OSNet ReID gallery (vector 256 array), FCM token, notification preferences
- **Camera** — RTSP URL, floor zone, homography matrix
- **Track** — a detected person blob in one camera; may link to a `Person.id`
- **GymSession** — one per person per visit; groups all tracks and sets
- **ExerciseSet** — one exercise type per set; stores rep count, form score, alerts
- **RepEvent** — TimescaleDB hypertable; individual rep with duration, joint flags
- **PoseFrame** — TimescaleDB; raw 33-keypoint snapshots (configurable retention)
- **Conversation / Message** — LLM chat thread per person
- **GymKnowledge** — RAG document store (pgvector embedding 384-d)
- **Notification** — audit log of sent guidance

### Redis Live State
- `track:{id}:state` — current bbox, keypoints, exercise, rep count
- `reid:gallery` — hot-cache of all person embeddings for sub-ms matching
- `person:{id}:ws_session` — WebSocket routing
- `set:{id}:rep_state` — state machine phase for ongoing set

---

## Phased Implementation Plan

---

### Phase 1 — Prototype: Single Camera, Anonymous Tracking, Basic Exercise + Mobile Companion (Weeks 1–8)

**Goal**: Working end-to-end pipeline on a single camera with no identity. Detect exercises, count reps, flag form issues. Mobile app delivers audio guidance via headphones and shows movement replay + training stats.

**Deployment**: Hybrid — CV pipeline on local GPU workstation, LLM calls to Anthropic cloud API.

#### Steps

**1.1 — Repo Scaffold & Shared Infrastructure (Days 1–5)**
- Init monorepo with `uv` for Python dependency management
- Create `shared/` package: SQLAlchemy 2.0 async ORM models, Alembic migrations, Redis client, structured logging
- `docker-compose.yml`: PostgreSQL+TimescaleDB, Redis, Nginx, MinIO
- Alembic migration: create all Phase 1 tables (`Camera`, `Track`, `GymSession`, `ExerciseSet`, `RepEvent`, `PoseFrame`)
- `Makefile` with: `make dev-up`, `make dev-down`, `make migrate`, `make test`
- `.env.example` with all required env vars

**1.2 — Video Ingestion Service (Days 5–10)**
- `services/ingestion/src/ingestion/camera_reader.py`: one thread per camera reading RTSP via `av` (hardware H.264 decode)
- Downsample to 15 FPS, compress to JPEG quality 85 before publishing
- `frame_publisher.py`: `XADD` to Redis Stream `frames:{camera_id}` with maxlen cap (e.g., 100 frames)
- Frame message schema: `{camera_id, timestamp_ns, frame_seq, jpeg_b64}`

**1.3 — Perception Pipeline (Days 8–16)**
- `services/perception/src/perception/detector.py`: YOLOv11-pose (nano or small) person detection + pose keypoints in one pass. Use `ultralytics` package.
- `tracker.py`: ByteTrack intra-camera tracker (built into Ultralytics). Assigns stable local `track_id` across frames.
- `reid_extractor.py`: OSNet-x1.0 appearance embedding per detected person crop (256-d, L2-normalized). Used later for cross-camera matching.
- `pipeline.py`: compose all three steps per frame. Publish enriched detection event to `perceptions:{camera_id}` Redis Stream.
- Detection event schema: `{camera_id, timestamp_ns, track_id, bbox, keypoints[33], reid_embedding[256]}`

**1.4 — Exercise Analysis Service (Days 14–24)**
- `exercise_registry.py`: YAML-driven exercise definitions (key joint pairs + angle thresholds for squat, push-up, bicep curl, lateral raise). Extensible — adding a new exercise means adding a YAML entry.
- `rep_counter.py`: per-track state machine. Tracks the angle of a primary joint. Transitions between `up`/`down` phases; increments rep count on each full cycle. Uses median filtering to reduce noise.
- `form_analyzer.py`: joint angle threshold checks per exercise. Emits `FormAlert` events when angles deviate (e.g., knee cave during squat).
- `classifier.py` (Phase 1 = heuristic, replaced by ONNX model in Phase 3): infer exercise type from which joint angles are most active.
- Persist `ExerciseSet` and `RepEvent` to TimescaleDB.
- Publish `form_alerts` and `rep_counted` events to Redis Streams.

**1.5 — LLM Guidance Service (Days 20–28)**
- `guidance/llm_client.py`: `AsyncAnthropic` wrapper, model `claude-sonnet-4-6`. Calls are async to avoid blocking the event loop.
- `guidance/form_alert_handler.py`: subscribes to `form_alerts` stream. Builds a short system prompt with exercise context, calls LLM, generates 1–2 sentence personalized correction. Rate-limit: at most 1 guidance message per 30 seconds per track.
- `guidance/notification_dispatcher.py`: routes message to WebSocket session or queues for mobile push.
- For Phase 1, guidance is delivered as text-to-speech audio on the user's phone (headphones).

**1.6 — API Gateway (Days 22–30)**
- `services/api/`: FastAPI app with:
  - `GET /sessions/{session_id}` — session summary
  - `GET /tracks/{track_id}/history` — exercise history for a track
  - `GET /tracks/{track_id}/replay` — list of video clip URLs for movement replay
  - `WS /ws/live/{track_id}` — real-time rep updates, form alerts, guidance text
- JWT auth (placeholder in Phase 1, proper in Phase 2)

**1.7 — Mobile App (Days 25–40)**
Phase 1 scope (minimal):
- Bluetooth/Wi-Fi connection screen: enter gym, scan QR code to get a `track_id` session token
- **Live coaching tab**: WebSocket connection receives guidance text → read aloud via native TTS (headphone output)
- **Movement replay tab**: list of short video clips (saved by the worker service), playable within the app
- **Stats tab**: session duration, exercises done, rep counts, form score per set
- React Native; iOS first, Android parity in Phase 2

**1.8 — Video Clip Worker (Days 28–35)**
- Ingestion service maintains a 15-second rolling frame buffer in memory per camera
- On form alert, Celery task saves the surrounding 5-second clip to MinIO as H.264 via PyAV
- Clip URL stored in `ExerciseSet.alerts` JSONB field
- Served via presigned MinIO URL in the mobile replay tab

**Phase 1 Verification**:
1. Start `make dev-up`, register a camera with `scripts/register_camera.py`
2. Run a test video through the pipeline; verify rep counts appear in TimescaleDB
3. Trigger a form alert; verify LLM guidance text appears on the WebSocket client
4. Open the mobile app on a phone, scan QR code, exercise in front of camera; verify audio guidance through headphones and replay clips

---

### Phase 2 — Person Identification & Personalized Experience (Weeks 9–18)

**Goal**: Link anonymous tracks to registered gym members. Real-time personalized guidance uses the member's name, history, and goals.

**New in Phase 2**:
- User registration: face enrollment + OSNet ReID gallery seeding
- Face recognition (InsightFace/ArcFace) as primary identity resolver
- QR code badge scan as fallback identity resolver
- Cross-camera ReID: OSNet cosine similarity matching against identity gallery
- Personalized LLM system prompts incorporating member profile and history
- Full conversation interface in the mobile app (chat with AI trainer)
- Workout history views

#### Steps

**2.1 — Person Registration (Days 1–7)**
- `scripts/register_person.py`: CLI tool — capture 5 face photos, extract ArcFace 512-d embedding via InsightFace, walk person in front of each camera to seed 10-frame OSNet appearance gallery
- `Person` record created; QR code generated and printed/emailed for fallback login
- `services/reid/src/reid/gallery_manager.py`: `upsert_embedding`, `search_gallery` (pgvector `<=>` cosine), Redis gallery cache refresh

**2.2 — ReID Identity Resolver (Days 5–16)**
- `services/reid/`: new service consuming perception stream
- `matcher.py`: for each new track, collect first 10 OSNet embeddings, average them, query gallery. If cosine similarity > 0.75 → link `track.global_person_id`. If face visible + ArcFace similarity > 0.85 → ground-truth override.
- Spatial-temporal gating: if track appears near a camera boundary within 10s of another track exiting, boost match score.
- `identity_resolver.py`: publishes `identity_resolved` events to Redis Stream.

**2.3 — Personalized Guidance (Days 12–22)**
- `guidance/prompt_builder.py`: builds system prompt including person's name, current goal, recent workout history, known injury notes from profile
- `tool_definitions.py`: LLM tools — `get_workout_history`, `get_exercise_stats`, `suggest_workout_plan`
- `tool_executor.py`: executes tool calls against DB/Redis

**2.4 — Conversation Manager (Days 16–28)**
- Full chat endpoint `POST /conversations/{conversation_id}/messages`
- Context window management: keep last 20 messages in Redis, summarize older ones via LLM
- RAG: semantic search of `gym_knowledge` table (pgvector), inject top-3 chunks into system prompt
- LLM encouragement: trigger motivational message when person completes a personal best

**2.5 — Mobile App Enhancement (Days 22–35)**
- Chat screen: conversational interface with the gym AI
- Profile screen: set goals, injury notes, notification preferences
- History screen: calendar heatmap + exercise breakdown

**Phase 2 Verification**:
1. Register a test person, verify ReID links correctly across 2+ cameras
2. Trigger a form alert; verify the guidance uses the person's name and history
3. Chat with the AI trainer; verify RAG context is used in responses
4. Verify QR code fallback correctly resolves identity

---

### Phase 3 — Multi-Camera Floor Plan, ML Classifier, Video Review, RAG Knowledge Base (Weeks 19–30)

**New in Phase 3**:
- Floor-plan homography: each camera maps pixel coords → 2D gym floor map (meters)
- Global track positions visible on admin dashboard map
- ML-trained TCN exercise classifier (replaces Phase 1 heuristics)
- Gym knowledge RAG database seeded with exercise guides, safety info
- In-gym display kiosks (zone-level motivational messages)
- Video clip review with LLM-generated timestamped form notes

#### Steps

**3.1 — Camera Calibration & Homography (Days 1–10)**
- `scripts/calibrate_camera.py`: click 4 floor points in camera image, enter real-world coordinates, compute `cv2.findHomography`, store in `cameras.homography_matrix`
- `shared/utils/geometry.py`: `pixel_to_floor(bbox_bottom_center, homography)` maps person positions to 2D floor coords
- Admin dashboard: live floor map with person positions by zone

**3.2 — Improved Cross-Camera ReID (Days 8–20)**
- Rolling-window median embedding (last 20 frames) instead of first-appearance single embedding
- Spatial-temporal constraint using floor-plan adjacency
- Tracklet re-association: keep lost tracks in "pending" state for 30 seconds before closing

**3.3 — ML Exercise Classifier (Days 12–24)**
- Train TCN in `ml/exercise_classifier/` on NTU RGB+D (public) + custom gym data
- Input: 30-frame window of 34 features (17 keypoints × x,y normalized to person bbox)
- Export to ONNX; deploy via ONNX Runtime in `exercise/classifier.py`
- `ml/data_collection/pose_recorder.py`: record labeled pose sequences for custom gym exercises

**3.4 — RAG Knowledge Base (Days 18–26)**
- `scripts/seed_gym_knowledge.py`: load exercise guides (proper form, common mistakes, variations), safety guidelines, nutrition basics
- `guidance/rag_retriever.py`: sentence-transformers embedding + pgvector `<=>` search, inject top-3 chunks into LLM context

**3.5 — In-Gym Kiosk Display (Days 24–32)**
- React web app (kiosk mode): live floor map, anonymous per-zone stats, motivational messages
- Opt-in public name display for leaderboard

**Phase 3 Verification**:
1. Camera calibration: verify person positions appear correctly on floor map
2. TCN classifier: measure accuracy on holdout set (target > 85%)
3. RAG: query LLM about a specific exercise and verify knowledge is retrieved

---

### Phase 4 — Production Hardening, Scale, Privacy & Advanced Features (Weeks 31–44)

**New in Phase 4**:
- Kafka replacing Redis Streams for durability and replay
- TensorRT model optimization (2–4× inference speedup)
- Kubernetes deployment with horizontal pod autoscaling
- GDPR/privacy framework (explicit consent, data deletion, encrypted biometrics)
- Fall detection (safety alert to staff)
- Workout plan persistence + LLM-driven progression tracking
- Multi-gym / multi-location support
- Integration with gym management system (membership, booking)
- A/B testing for guidance message effectiveness

#### Key Steps

**4.1 — Kafka Migration**: Topics `gym.frames.{cam}`, `gym.perceptions.{cam}`, `gym.exercise_events`, `gym.form_alerts`, `gym.guidance`. Redis stays for live state cache.

**4.2 — TensorRT Optimization**: Export YOLOv11, OSNet, and TCN to TensorRT engines (FP16). Expected: YOLO 15 → 60+ FPS per GPU.

**4.3 — Kubernetes**: GPU node selector for perception pods, HPA on guidance service by queue depth, managed PostgreSQL (Cloud SQL / RDS), cert-manager TLS.

**4.4 — Privacy Framework**: Default = anonymous tracking. Face/ReID identity linking requires explicit opt-in. GDPR Article 17 cascade delete. Biometric embeddings encrypted at rest with per-person keys.

**4.5 — Fall Detection**: Rapid head-below-hip keypoint transition across 3+ frames → immediate high-priority staff alert. Context filter: exclude known floor exercises.

---

## Critical Technical Challenges

| Challenge | Mitigation |
|---|---|
| Cross-camera ReID accuracy (similar gym clothing) | Fine-tune OSNet on gym-specific data; face recognition as ground-truth override; spatial-temporal gating |
| LLM latency (form corrections must arrive quickly) | Template library for 10 most common form issues (no LLM); LLM runs async after alert fires; cache identical corrections |
| Real-time frame throughput (many cameras × 15 FPS) | Redis Stream maxlen cap; skip frames under load; TensorRT in Phase 4 |
| Person re-identification after appearance change | Rolling-window median embedding; multi-cue fusion (color histogram + deep features) |
| Privacy and biometric data regulations | Opt-in model; encrypted embeddings; auto-expiry on video clips; full audit log |

---

## Verification — End-to-End Test Scenarios

1. **Anonymous rep counting**: Run a pre-recorded exercise video through the pipeline; verify `RepEvent` rows in TimescaleDB match expected reps
2. **Identity resolution**: Register a test person, walk in front of two cameras; verify `track.global_person_id` is populated on both tracks with the correct person
3. **Real-time guidance delivery**: Do a squat with intentional bad form; verify audio guidance plays through headphones within 3 seconds
4. **Conversation**: Open mobile app chat, ask "what's my squat progress this week?"; verify LLM returns data from `ExerciseSet` history
5. **Movement replay**: Complete a set; verify video clip appears in the mobile replay tab within 30 seconds
6. **QR code fallback**: Disable face recognition, scan QR code on mobile, start exercising; verify identity is correctly linked

---

## Files to Create (Phase 1 Bootstrap)

| File | Purpose |
|---|---|
| `docker-compose.yml` | PostgreSQL+TimescaleDB, Redis, MinIO, Nginx |
| `shared/src/gym_shared/db/models.py` | All SQLAlchemy ORM models |
| `shared/src/gym_shared/db/migrations/` | Alembic migrations |
| `services/ingestion/src/ingestion/camera_reader.py` | RTSP stream reader |
| `services/perception/src/perception/pipeline.py` | YOLO + pose + ReID per frame |
| `services/exercise/src/exercise/rep_counter.py` | State machine rep counting |
| `services/exercise/src/exercise/form_analyzer.py` | Joint angle threshold checks |
| `services/exercise/data/exercises.yaml` | Exercise definitions |
| `services/guidance/src/guidance/llm_client.py` | Anthropic SDK wrapper |
| `services/guidance/src/guidance/form_alert_handler.py` | Alert → LLM → notification |
| `services/api/src/api/main.py` | FastAPI app factory |
| `services/worker/src/worker/tasks/video_clip.py` | Celery clip save task |
| `scripts/setup_db.py` | Initialize schema |
| `scripts/register_camera.py` | Add camera to system |
| `Makefile` | Dev commands |
