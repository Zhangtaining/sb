# CLAUDE.md - Autonomous Workflow Instructions

## Project Context

**Project:** Smart Gym System
**Description:** Multi-camera gym system that tracks exercises, identifies members, and delivers personalized AI coaching via LLM
**Tech Stack:** Python 3.11, FastAPI, YOLOv11, MediaPipe, OSNet (ReID), InsightFace, Claude claude-sonnet-4-6 (Anthropic SDK), PostgreSQL + TimescaleDB + pgvector, Redis, MinIO, React Native, Docker Compose
**Entry Point:** `make dev-up` (starts all services via Docker Compose)
**Test Command:** `make test`

### Architecture Overview
```
smart-gym/
├── services/
│   ├── ingestion/      # RTSP stream reader → Redis Streams
│   ├── perception/     # YOLO detection + pose estimation + ReID feature extraction
│   ├── reid/           # Cross-camera identity resolver
│   ├── exercise/       # Rep counting, form analysis, exercise classification
│   ├── guidance/       # LLM conversations, RAG retrieval, notification dispatch
│   ├── api/            # FastAPI REST + WebSocket gateway
│   └── worker/         # Celery async tasks (video clips, push notifications)
├── shared/             # Internal Python package shared across services
│   └── src/gym_shared/
│       ├── db/         # SQLAlchemy 2.0 async ORM models + Alembic migrations
│       ├── events/     # Redis Streams event schemas (Pydantic)
│       └── utils/      # Geometry (homography), logging
├── ml/                 # Offline ML training (exercise TCN, ReID fine-tuning)
├── scripts/            # DB setup, camera registration, person enrollment
├── infrastructure/     # Docker Compose, Nginx, Prometheus, Grafana
├── docs/
│   ├── tasks.md        # Task tracking (source of truth for all work)
│   └── progress.md     # Session-by-session progress log
├── PLAN.md             # Full phased implementation plan (reference)
└── Makefile            # Common dev commands
```

### Key Conventions
- Snake_case for files and variables, PascalCase for classes
- All services use `uv` for Python dependency management
- SQLAlchemy 2.0 style: `Mapped[T]` and `mapped_column()` throughout
- Async-first: all DB queries and external calls use `async/await`
- Pydantic v2 for all event schemas and API request/response models
- Each service has its own `pyproject.toml` and `Dockerfile`
- Environment config via Pydantic `BaseSettings` (reads from `.env`)
- Structured logging via `structlog` across all services
- Redis Stream key convention: `{domain}:{camera_id}` (e.g., `frames:cam-01`, `perceptions:cam-01`)

---

## Workflow

### Phase 1: Task Breakdown

When given a design doc, feature request, or bug report:

1. **Understand fully** — Read everything. Identify unknowns.
2. **Ask clarifying questions** before breaking down (don't assume)
3. **Create `docs/tasks.md`** if it doesn't exist
4. **Break into small tasks** — Each task should be:
   - Completable in one focused session (< 30 min of work)
   - Independently verifiable
   - Focused on one concern
5. **Order by dependency** — Prerequisite tasks first
6. **Identify risks** — Flag tasks that might need human input

**Task Format:**
```markdown
## Task [ID]: [Short Title]

- **Status:** `IN_QUEUE` | `IN_PROGRESS` | `COMPLETE` | `BLOCKED`
- **Description:** [What to do — be specific]
- **Why:** [Context on why this matters]
- **Expected Results:** [Concrete deliverable]
- **Verification:**
  - [ ] [Specific check — "make test passes", "endpoint returns 200"]
  - [ ] [Another check]
- **After Completion:**
  - [ ] All verification checks above pass
  - [ ] Run `git status` — confirm only intended files changed
  - [ ] `git add <specific files>` and commit: `feat(<scope>): <description>\n\nTask: #[ID]`
  - [ ] `git push origin main`
  - [ ] Update status to `COMPLETE` in `docs/tasks.md`
  - [ ] Append entry to `docs/progress.md`
- **Dependencies:** [Task IDs or "None"]
- **Notes:** [Optional — gotchas, hints, related files]
```

---

### Phase 2: Pick Up Task

When asked to continue or pick up work:

1. **Read `docs/progress.md`** — Understand where things stand
2. **Read `docs/tasks.md`** — Find first `IN_QUEUE` task with all dependencies `COMPLETE`
3. **If no eligible task exists:**
   - Check for `BLOCKED` tasks and report why they're blocked
   - Or report that all tasks are complete
4. **Set status to `IN_PROGRESS`**
5. **Announce:** "Starting Task [ID]: [Title]"

---

### Phase 3: Before Implementation Checklist

Before writing code:

- [ ] I understand what "done" looks like for this task
- [ ] I've reviewed relevant existing code
- [ ] I know which files I'll likely modify
- [ ] I've checked for similar patterns in the codebase to follow
- [ ] If unsure about approach, I've asked the human

---

### Phase 4: Implementation

1. **Work incrementally** — Small changes, verify often
2. **Follow existing patterns** — Match the codebase style, don't introduce new conventions
3. **Stay in scope** — If you notice other issues, note them for a future task, don't fix now
4. **Test as you go** — Don't wait until the end

---

### Phase 5: Verification

Before marking complete:

1. **Run verification checks** listed in the task
2. **Run full test suite** — Ensure no regressions
3. **Manual smoke test** if applicable
4. **If any check fails:**
   - Fix the issue
   - Re-run ALL checks (not just the failing one)
   - Repeat until all pass

**Do not proceed to commit if verification fails.**

---

### Phase 6: Git Commit

1. **Review diff:** `git diff` — Make sure only intended changes are included
2. **Stage files:** `git add <specific-files>` (avoid `git add .` unless certain)
3. **Commit with conventional message:**
   ```
   <type>(<scope>): <short description>

   [Optional body explaining why]

   Task: #[ID]
   ```
4. **Push:** `git push origin <branch>`

**Types:** feat | fix | refactor | test | docs | chore

---

### Phase 7: Update Progress

1. **Update task status** to `COMPLETE` in `docs/tasks.md`
2. **Append to `docs/progress.md`:**

```markdown
## [Date] - Task [ID]: [Title]

**Summary:** [What was done — 2-3 sentences]

**Changes:**
- `file.py` — [what changed]

**Decisions Made:** [Any non-obvious choices and why]

**Context for Next Session:** [What the next person/session should know]

**Commit:** [short hash]
```

---

### Phase 8: Asking for Help

**Try these first (spend max 5-10 min):**
1. Re-read the task and any related docs
2. Search the codebase for similar patterns
3. Check error messages carefully
4. Try a simpler approach

**Then ask the human when:**
- Requirements are ambiguous
- Multiple valid approaches exist (need a decision)
- Blocked by external factors (credentials, access, etc.)
- Tests fail in ways I can't diagnose
- Task is larger than expected (needs re-scoping)
- I've tried 2-3 approaches and none work

**Format:**
```
🛑 NEED INPUT

**Task:** [ID] - [Title]
**Blocker:** [What's stopping progress]
**What I tried:** [Brief list]
**Options:** [If applicable]
**Question:** [Specific question]
```

---

## Recovery Procedures

### If Tests Break
1. `git stash` or `git diff > backup.patch` — Save current work
2. `git checkout .` — Reset to clean state
3. Verify tests pass on clean state
4. Re-apply changes incrementally to find the problem

### If Stuck in a Loop
1. Stop and document what's happening
2. `git stash` current work
3. Ask human with full context

### If Unsure About a Change
- Make the change on a branch
- Ask human to review before merging

---

## Session Start Checklist

When starting any session:

- [ ] Read this CLAUDE.md
- [ ] Read `docs/progress.md` (last 2-3 entries)
- [ ] Check `docs/tasks.md` for current state
- [ ] Run tests to verify clean starting state
- [ ] Confirm git status is clean (or understand uncommitted changes)

---

## Session End Checklist

Before ending a session:

- [ ] Current task is either `COMPLETE` or status reflects true state
- [ ] Progress.md is updated
- [ ] All changes are committed (or stashed with a note in progress.md)
- [ ] No failing tests left unexplained
- [ ] Next steps are clear for the next session

---

## Principles

1. **Verify, don't assume** — Run the checks, don't just believe it works
2. **Small steps** — Easier to debug, easier to review
3. **Document decisions** — Future sessions need context
4. **Ask early** — 5 minutes of clarification beats 30 minutes of wrong work
5. **Stay in scope** — Note other issues, don't derail current task
6. **Leave it better** — Next session should have clear context to continue
7. **Wrap up at token limits** — If you are approaching context/token limits, stop starting new work. Finish the current atomic step, update the task status in `docs/tasks.md` to `IN_PROGRESS` with a clear note on exactly where you stopped, append a "Context for Next Session" entry to `docs/progress.md`, and commit any completed changes. The next agent must be able to pick up exactly where you left off without guessing.
