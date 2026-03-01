"""Exercise analysis pipeline.

Consumes PerceptionEvents from Redis Stream, runs:
  HeuristicClassifier → RepCounter → FormAnalyzer

Persists ExerciseSet + RepEvent rows to TimescaleDB.
Publishes RepCountedEvent and FormAlertEvent to Redis Streams.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

import redis.asyncio as aioredis

from gym_shared.db.models import ExerciseSet, GymSession, RepEvent, Track
from gym_shared.db.session import get_db
from gym_shared.events.publisher import (
    GROUP_EXERCISE,
    ack,
    ensure_consumer_group,
    perceptions_stream,
    publish,
    read_group,
)
from gym_shared.events.schemas import FormAlertEvent, PerceptionEvent, RepCountedEvent
from gym_shared.logging import get_logger

from exercise.classifier import HeuristicClassifier
from exercise.config import ExerciseConfig
from exercise.exercise_registry import ExerciseRegistry
from exercise.form_analyzer import FormAnalyzer
from exercise.rep_counter import RepCounter

log = get_logger(__name__)

_STREAM_REP_COUNTED = "rep_counted"
_STREAM_FORM_ALERTS = "form_alerts"


class ExercisePipeline:
    """Processes PerceptionEvents for a single camera."""

    def __init__(
        self,
        camera_id: str,
        config: ExerciseConfig,
        registry: ExerciseRegistry,
    ) -> None:
        self._camera_id = camera_id
        self._cfg = config
        self._registry = registry
        self._in_stream = perceptions_stream(camera_id)

        self._classifier = HeuristicClassifier(registry)
        # exercise_name → RepCounter
        self._rep_counters: dict[str, RepCounter] = {
            name: RepCounter(
                registry.get_exercise(name),
                set_idle_timeout_s=config.set_idle_timeout_s,
            )
            for name in registry.list_exercises()
        }
        # exercise_name → FormAnalyzer
        self._form_analyzers: dict[str, FormAnalyzer] = {
            name: FormAnalyzer(registry.get_exercise(name))
            for name in registry.list_exercises()
        }
        # track_id → current exercise name
        self._track_exercise: dict[int, str] = {}
        # track_id → db Track UUID (str)
        self._track_db_ids: dict[int, str] = {}
        # track_id → db ExerciseSet UUID (str)
        self._track_set_ids: dict[int, str] = {}
        # track_id → active GymSession UUID (str)
        self._track_session_ids: dict[int, str] = {}

        self._frame_count = 0
        self._t_start = time.monotonic()

    async def run(self, redis: aioredis.Redis) -> None:
        await ensure_consumer_group(redis, self._in_stream, GROUP_EXERCISE)
        log.info(
            "exercise_pipeline_starting",
            camera_id=self._camera_id,
            stream=self._in_stream,
        )
        while True:
            messages = await read_group(
                redis,
                self._in_stream,
                GROUP_EXERCISE,
                self._cfg.consumer_name,
                count=self._cfg.read_batch,
                block_ms=self._cfg.block_ms,
            )
            for msg_id, msg_data in messages:
                try:
                    await self._process(redis, msg_id, msg_data)
                except Exception as exc:
                    log.error(
                        "exercise_pipeline_error",
                        camera_id=self._camera_id,
                        msg_id=msg_id,
                        error=str(exc),
                    )
                    await ack(redis, self._in_stream, GROUP_EXERCISE, msg_id)

    async def _process(
        self, redis: aioredis.Redis, msg_id: str, msg_data: dict
    ) -> None:
        event = PerceptionEvent.model_validate_json(msg_data.get("data", "{}"))
        track_id = event.track_id

        # Classify exercise from rolling keypoint history
        exercise_name, confidence = self._classifier.update(track_id, event.keypoints)

        if exercise_name == "unknown" or confidence < 0.5:
            await ack(redis, self._in_stream, GROUP_EXERCISE, msg_id)
            return

        self._track_exercise[track_id] = exercise_name
        rep_counter = self._rep_counters[exercise_name]
        form_analyzer = self._form_analyzers[exercise_name]
        exercise_def = self._registry.get_exercise(exercise_name)

        # Compute primary joint angle
        from exercise.keypoint_utils import get_joint_angle
        a, b, c = exercise_def.primary_joint
        angle = get_joint_angle(event.keypoints, a, b, c)

        # Ensure DB records exist for this track
        set_id = await self._ensure_db_records(track_id, exercise_name, event)

        # Run rep counter
        rep_event = rep_counter.update(track_id, angle, event.timestamp_ns)
        if rep_event is not None:
            rep_event = RepCountedEvent(
                camera_id=self._camera_id,
                track_id=rep_event.track_id,
                exercise_set_id=set_id,
                exercise_type=rep_event.exercise_type,
                rep_number=rep_event.rep_number,
                rep_count=rep_event.rep_count,
                duration_ms=rep_event.duration_ms,
                phase=rep_event.phase,
                timestamp_ns=rep_event.timestamp_ns,
            )
            await publish(redis, _STREAM_REP_COUNTED, rep_event)
            await self._persist_rep_event(rep_event, set_id)
            log.info(
                "rep_counted",
                camera_id=self._camera_id,
                track_id=track_id,
                exercise=exercise_name,
                rep=rep_event.rep_number,
            )

        # Run form analyzer
        alerts = form_analyzer.check(
            track_id=track_id,
            keypoints=event.keypoints,
            exercise_set_id=set_id,
            rep_count=rep_counter.get_rep_count(track_id),
            timestamp_ns=event.timestamp_ns,
        )
        for alert in alerts:
            filled_alert = FormAlertEvent(
                camera_id=self._camera_id,
                track_id=alert.track_id,
                exercise_set_id=set_id,
                exercise_type=alert.exercise_type,
                rep_count=alert.rep_count,
                alert_key=alert.alert_key,
                alert_message=alert.alert_message,
                severity=alert.severity,
                joint_angles=alert.joint_angles,
                timestamp_ns=alert.timestamp_ns,
            )
            await publish(redis, _STREAM_FORM_ALERTS, filled_alert)
            log.info(
                "form_alert",
                camera_id=self._camera_id,
                track_id=track_id,
                alert_key=alert.alert_key,
            )

        self._frame_count += 1
        if self._frame_count % 100 == 0:
            elapsed = time.monotonic() - self._t_start
            log.info(
                "exercise_pipeline_throughput",
                camera_id=self._camera_id,
                frames=self._frame_count,
                fps=round(self._frame_count / elapsed, 1),
            )

        await ack(redis, self._in_stream, GROUP_EXERCISE, msg_id)

    async def _ensure_db_records(
        self, track_id: int, exercise_name: str, event: PerceptionEvent
    ) -> str:
        """Create Track, GymSession, ExerciseSet rows if not already created."""
        if track_id in self._track_set_ids:
            return self._track_set_ids[track_id]

        now = datetime.now(timezone.utc)
        async with get_db() as db:
            # Create a GymSession for this anonymous track
            session = GymSession(
                id=uuid.uuid4(),
                started_at=now,
                primary_track_ids=[str(track_id)],
            )
            db.add(session)
            await db.flush()

            # Create a Track record
            track = Track(
                id=uuid.uuid4(),
                camera_id=self._camera_id,
                local_track_id=track_id,
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(track)
            await db.flush()

            # Create an ExerciseSet
            ex_set = ExerciseSet(
                id=uuid.uuid4(),
                session_id=session.id,
                track_id=track.id,
                exercise_type=exercise_name,
                started_at=now,
                classifier_confidence=0.0,
            )
            db.add(ex_set)
            await db.flush()

            set_id = str(ex_set.id)

        self._track_session_ids[track_id] = str(session.id)
        self._track_db_ids[track_id] = str(track.id)
        self._track_set_ids[track_id] = set_id
        log.info(
            "db_records_created",
            camera_id=self._camera_id,
            track_id=track_id,
            exercise=exercise_name,
            set_id=set_id,
        )
        return set_id

    async def _persist_rep_event(self, event: RepCountedEvent, set_id: str) -> None:
        now = datetime.now(timezone.utc)
        async with get_db() as db:
            rep = RepEvent(
                time=now,
                exercise_set_id=uuid.UUID(set_id),
                rep_number=event.rep_number,
                duration_ms=event.duration_ms,
                phase=event.phase,
            )
            db.add(rep)
