"""WebSocket connection manager — fan-out Redis Streams events to connected clients."""
from __future__ import annotations

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import WebSocket

from gym_shared.logging import get_logger

log = get_logger(__name__)

# Redis streams the manager subscribes to
_STREAMS = ["rep_counted", "form_alerts", "guidance", "set_complete", "rest_timer"]

# How to map a Redis stream message to the event type field sent over WS
_STREAM_TYPE_MAP = {
    "rep_counted": "rep_counted",
    "form_alerts": "form_alert",
    "guidance": "guidance",
    "set_complete": "set_complete",
    "rest_timer": "rest_update",
}


class WebSocketManager:
    """Registry of active WebSocket connections keyed by track_id.

    Runs a background task that reads from Redis Streams and fans out
    messages to the correct connected client.
    """

    def __init__(self) -> None:
        # track_id (str) → WebSocket
        self._connections: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(self, track_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections[track_id] = ws
        log.info("ws_connected", track_id=track_id)

    async def disconnect(self, track_id: str) -> None:
        async with self._lock:
            self._connections.pop(track_id, None)
        log.info("ws_disconnected", track_id=track_id)

    async def send(self, track_id: str, message: dict) -> None:
        async with self._lock:
            ws = self._connections.get(track_id)
        if ws is None:
            return
        try:
            await ws.send_text(json.dumps(message))
        except Exception as exc:
            log.warning("ws_send_error", track_id=track_id, error=str(exc))
            await self.disconnect(track_id)

    async def broadcast_to_all(self, message: dict) -> None:
        async with self._lock:
            targets = list(self._connections.items())
        for track_id, ws in targets:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                await self.disconnect(track_id)

    # ── Background Redis reader ────────────────────────────────────────────────

    async def _read_stream(
        self,
        redis: aioredis.Redis,
        stream: str,
        last_id: str,
    ) -> tuple[str, list[tuple[bytes, dict]]]:
        """Read new messages from one stream since `last_id`."""
        try:
            results = await redis.xread({stream: last_id}, count=10, block=100)
            if not results:
                return last_id, []
            _, messages = results[0]
            new_last_id = messages[-1][0].decode()
            return new_last_id, messages
        except Exception as exc:
            log.error("ws_redis_read_error", stream=stream, error=str(exc))
            return last_id, []

    def _extract_track_id(self, stream: str, data: dict) -> str | None:
        """Pull track_id out of a stream message payload."""
        # All our event schemas carry 'data' field as JSON string
        raw = data.get(b"data") or data.get("data")
        if not raw:
            return None
        try:
            payload = json.loads(raw if isinstance(raw, str) else raw.decode())
        except Exception:
            return None
        # RepCountedEvent / FormAlertEvent carry track_id; GuidanceMessage carries track_id
        return str(payload.get("track_id")) if payload.get("track_id") is not None else None

    async def run_reader(self, redis: aioredis.Redis) -> None:
        """Long-running task: reads all streams and routes messages to WS clients."""
        last_ids = {stream: "$" for stream in _STREAMS}
        log.info("ws_manager_reader_started", streams=_STREAMS)

        while True:
            for stream in _STREAMS:
                last_id, messages = await self._read_stream(redis, stream, last_ids[stream])
                last_ids[stream] = last_id

                for _msg_id, data in messages:
                    track_id = self._extract_track_id(stream, data)
                    if track_id is None:
                        continue

                    raw = data.get(b"data") or data.get("data")
                    try:
                        payload = json.loads(raw if isinstance(raw, str) else raw.decode())
                    except Exception:
                        continue

                    event_type = _STREAM_TYPE_MAP[stream]
                    await self.send(track_id, {"type": event_type, "data": payload})

            # Brief yield so we don't busy-loop when all streams are empty
            await asyncio.sleep(0.05)
