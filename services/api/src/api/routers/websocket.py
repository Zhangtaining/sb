"""WS /ws/live/{track_id} — real-time rep counts, form alerts, guidance."""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from gym_shared.logging import get_logger

from api.websocket_manager import WebSocketManager

log = get_logger(__name__)

router = APIRouter(tags=["websocket"])

# Manager is injected via app.state in main.py
_manager: WebSocketManager | None = None


def set_manager(manager: WebSocketManager) -> None:
    global _manager  # noqa: PLW0603
    _manager = manager


@router.websocket("/ws/live/{track_id}")
async def ws_live(track_id: str, websocket: WebSocket) -> None:
    manager = _manager
    if manager is None:
        await websocket.close(code=1011)
        return

    await manager.connect(track_id, websocket)
    try:
        while True:
            # Keep connection alive; client may send pings (we echo them)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(track_id)
