"""Redis Streams publisher and consumer helpers."""
from __future__ import annotations

import time

from redis.asyncio import Redis

from gym_shared.events.schemas import (
    FormAlertEvent,
    FrameMessage,
    GuidanceMessage,
    IdentityResolvedEvent,
    PerceptionEvent,
    RepCountedEvent,
    _FrozenModel,
)

# Stream name constants
STREAM_FRAMES = "frames:{camera_id}"
STREAM_PERCEPTIONS = "perceptions:{camera_id}"
STREAM_REP_COUNTED = "rep_counted"
STREAM_FORM_ALERTS = "form_alerts"
STREAM_GUIDANCE = "guidance"
STREAM_IDENTITY_RESOLVED = "identity_resolved"

# Consumer group names
GROUP_PERCEPTION = "perception-workers"
GROUP_EXERCISE = "exercise-workers"
GROUP_GUIDANCE = "guidance-workers"
GROUP_REID = "reid-workers"
GROUP_API = "api-fanout"


def frames_stream(camera_id: str) -> str:
    return f"frames:{camera_id}"


def perceptions_stream(camera_id: str) -> str:
    return f"perceptions:{camera_id}"


async def publish(
    redis: Redis,
    stream: str,
    event: _FrozenModel,
    maxlen: int = 1000,
) -> str:
    """Serialize a Pydantic event and XADD it to a Redis Stream.

    Args:
        redis: Async Redis client.
        stream: Stream name.
        event: A frozen Pydantic model instance.
        maxlen: Approximate max stream length (MAXLEN ~).

    Returns:
        The Redis message ID of the newly added entry.
    """
    payload = {"data": event.model_dump_json()}
    msg_id = await redis.xadd(stream, payload, maxlen=maxlen, approximate=True)
    return msg_id.decode() if isinstance(msg_id, bytes) else msg_id


async def ensure_consumer_group(
    redis: Redis,
    stream: str,
    group: str,
) -> None:
    """Create a consumer group if it does not exist, creating the stream too."""
    try:
        await redis.xgroup_create(stream, group, id="0", mkstream=True)
    except Exception as exc:
        # BUSYGROUP error means the group already exists — that's fine
        if "BUSYGROUP" not in str(exc):
            raise


async def read_group(
    redis: Redis,
    stream: str,
    group: str,
    consumer: str,
    count: int = 10,
    block_ms: int = 1000,
) -> list[tuple[str, dict]]:
    """Read messages from a consumer group.

    Returns a list of (message_id, data_dict) tuples.
    """
    results = await redis.xreadgroup(
        groupname=group,
        consumername=consumer,
        streams={stream: ">"},
        count=count,
        block=block_ms,
    )
    if not results:
        return []
    messages = []
    for _stream, entries in results:
        for msg_id, fields in entries:
            msg_id_str = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
            decoded = {
                k.decode() if isinstance(k, bytes) else k: (
                    v.decode() if isinstance(v, bytes) else v
                )
                for k, v in fields.items()
            }
            messages.append((msg_id_str, decoded))
    return messages


async def ack(redis: Redis, stream: str, group: str, *msg_ids: str) -> None:
    """Acknowledge processed messages."""
    await redis.xack(stream, group, *msg_ids)


def now_ns() -> int:
    """Current monotonic time in nanoseconds."""
    return time.monotonic_ns()
