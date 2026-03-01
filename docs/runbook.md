# Smart Gym System — Operations Runbook

> Everything you need to start, update, and shut down the system.

---

## Prerequisites (install once)

| Tool | Install |
|---|---|
| Docker Desktop | https://www.docker.com/products/docker-desktop |
| uv (Python package manager) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js ≥ 18 | https://nodejs.org |
| ffmpeg (for webcam streaming) | `brew install ffmpeg` |
| mediamtx (for webcam RTSP) | `brew install mediamtx` |
| wscat (for WebSocket testing) | `npm install -g wscat` |

---

## First-Time Setup (do this once)

```bash
cd /Users/tainingzhang/Workspace/sb

# 1. Create your .env file
cp .env.example .env
# Then open .env and fill in your API keys (see "Configuration" section below)

# 2. Start infrastructure
make dev-up

# 3. Apply database migrations
make migrate

# 4. Register your camera
make register-camera id=cam-01 url=rtsp://YOUR_CAMERA_URL zone=weights
```

After this, you never need to run steps 2–4 again unless you wipe the database.

---

## Daily Start

```bash
# 1. Make sure Docker Desktop is open (check the whale icon in menu bar)

# 2. Start everything
make dev-start
```

Wait ~10 seconds, then verify:
```bash
# Check infrastructure containers
docker compose ps

# Check API is responding
curl http://localhost:8000/healthz
# Expected: {"status":"ok"}
```

---

## Daily Stop

```bash
make dev-stop        # stops all 6 Python services

make dev-down        # stops Docker infrastructure (db, redis, minio)
```

> **Tip:** If you only want to stop services temporarily (keep the DB running), just run `make dev-stop`. Run `make dev-down` only when you're done for the day.

---

## Checking Logs

Each service writes logs to `/tmp/gym-<name>.log`:

```bash
tail -f /tmp/gym-api.log          # API gateway
tail -f /tmp/gym-guidance.log     # LLM calls and coaching messages
tail -f /tmp/gym-exercise.log     # rep counting and form alerts
tail -f /tmp/gym-perception.log   # YOLO detection
tail -f /tmp/gym-ingestion.log    # camera frame reading
tail -f /tmp/gym-worker.log       # video clip saving
```

For Docker infrastructure logs:
```bash
make logs s=db       # PostgreSQL
make logs s=redis    # Redis
make logs s=minio    # MinIO
```

---

## Configuration

All settings live in `.env` at the project root. Key variables:

```bash
# ── LLM Provider ──────────────────────────────────────────────────────────────
LLM_PROVIDER=gemini              # "anthropic" or "gemini"
GEMINI_API_KEY=your-key-here     # get from aistudio.google.com
ANTHROPIC_API_KEY=sk-ant-...     # get from console.anthropic.com
LLM_MODEL=gemini-2.5-flash       # gemini-2.5-flash | claude-sonnet-4-6

# ── Camera ────────────────────────────────────────────────────────────────────
CAMERA_IDS=cam-01                # comma-separated if multiple cameras
CAMERA_CAM_01_RTSP_URL=rtsp://192.168.1.50:8554/live

# ── Performance ───────────────────────────────────────────────────────────────
INGEST_FPS=15                    # frames per second to process
GUIDANCE_RATE_LIMIT_SECONDS=30   # min seconds between coaching messages per person
```

After changing `.env`, restart services:
```bash
make dev-stop && make dev-start
```

---

## Switching LLM Provider

**To use Gemini:**
```bash
# In .env:
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key-here
LLM_MODEL=gemini-2.5-flash
```

**To use Anthropic Claude:**
```bash
# In .env:
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-6
```

Then restart: `make dev-stop && make dev-start`

---

## Adding or Changing a Camera

**Add a new camera:**
```bash
make register-camera id=cam-02 url=rtsp://192.168.1.51:554/stream zone=cardio
```

Then update `.env`:
```bash
CAMERA_IDS=cam-01,cam-02
CAMERA_CAM_02_RTSP_URL=rtsp://192.168.1.51:554/stream
```

Restart: `make dev-stop && make dev-start`

**Using your Mac webcam (no IP camera):**
```bash
# Terminal 1 — start RTSP server
mediamtx

# Terminal 2 — push webcam to RTSP server
ffmpeg -f avfoundation -framerate 15 -video_size 1280x720 \
  -i "0" -vcodec libx264 -preset ultrafast -tune zerolatency \
  -f rtsp rtsp://localhost:8554/webcam

# Then in .env:
CAMERA_CAM_01_RTSP_URL=rtsp://localhost:8554/webcam
```

**Using iPhone as camera:**
1. Install "RTSP Camera Server" from the App Store
2. Open the app — it shows a URL like `rtsp://192.168.1.50:8554/live`
3. Set `CAMERA_CAM_01_RTSP_URL=rtsp://192.168.1.50:8554/live` in `.env`
4. Make sure iPhone and Mac are on the same WiFi

---

## Updating the Code

```bash
git pull origin main
uv sync                      # install any new Python dependencies
make dev-stop && make dev-start
```

If database models changed (new migration):
```bash
git pull origin main
make dev-stop
make migrate                 # apply new migrations
make dev-start
```

---

## Testing the Pipeline (quick smoke test)

```bash
# 1. Check API health
curl http://localhost:8000/healthz

# 2. Open API docs in browser
open http://localhost:8000/docs

# 3. Connect a WebSocket listener
wscat -c "ws://localhost:8000/ws/live/test-track"

# 4. Check what's in the database after running a video
docker exec gym-db psql -U gym -d gymdb \
  -c "SELECT exercise_type, rep_count, form_score FROM exercise_sets ORDER BY started_at DESC LIMIT 10;"

# 5. Run the visualizer on a video file (no services needed)
uv run python scripts/visualize_video.py input.mp4 output.mp4
open output.mp4
```

---

## Wiping Everything and Starting Fresh

```bash
# Stop all services and containers
make dev-stop
make dev-clean          # removes all Docker volumes (deletes DB, Redis, MinIO data)

# Start fresh
make dev-up
make migrate
make register-camera id=cam-01 url=rtsp://YOUR_URL zone=weights
make dev-start
```

---

## Troubleshooting

**Port 8000 already in use:**
```bash
lsof -i :8000 -n -P          # see what's using it
kill <PID>                    # kill it
```

**Services start but no events appear:**
- Check the camera URL is correct and reachable: `ffplay rtsp://YOUR_URL`
- Check Redis is running: `docker compose ps`
- Check ingestion logs: `tail -f /tmp/gym-ingestion.log`

**LLM guidance not working:**
- Check your API key in `.env`
- Check guidance logs: `tail -f /tmp/gym-guidance.log`
- Make sure `LLM_MODEL` matches your provider (e.g. `gemini-2.5-flash` for Gemini)

**Database errors on startup:**
```bash
make migrate    # re-run migrations
```

**`make dev-start` fails for one service:**
```bash
# Run that service manually to see the full error:
uv run --project services/guidance python -m guidance.main
```

---

## Service URLs

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| MinIO console (file browser) | http://localhost:9001 (user: minioadmin / minioadmin) |
| PostgreSQL | localhost:5432 (user: gym / gympass / gymdb) |
| Redis | localhost:6379 |
