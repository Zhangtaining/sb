#!/usr/bin/env python3
"""Register a camera in the PostgreSQL database.

Usage:
    python scripts/register_camera.py \
        --id cam-01 \
        --rtsp-url rtsp://192.168.1.10/live \
        --zone "weights-floor" \
        --description "Left corner facing squat rack"
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from gym_shared.db.models import Camera
from gym_shared.db.session import get_db
from gym_shared.logging import configure_logging, get_logger
from gym_shared.settings import settings

configure_logging(settings.log_format, settings.log_level)
log = get_logger(__name__)


async def register(camera_id: str, rtsp_url: str, zone: str, description: str) -> None:
    async with get_db() as db:
        existing = await db.get(Camera, camera_id)
        if existing:
            print(f"Error: camera '{camera_id}' already exists.", file=sys.stderr)
            sys.exit(1)

        camera = Camera(
            id=camera_id,
            location_description=description,
            rtsp_url=rtsp_url,
            floor_zone=zone,
        )
        db.add(camera)
        await db.flush()
        print(f"Camera registered: {camera.id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a gym camera")
    parser.add_argument("--id", required=True, help="Unique camera ID (e.g. cam-01)")
    parser.add_argument("--rtsp-url", required=True, help="RTSP stream URL")
    parser.add_argument("--zone", required=True, help="Floor zone label")
    parser.add_argument(
        "--description", default="", help="Human-readable location description"
    )
    args = parser.parse_args()
    asyncio.run(register(args.id, args.rtsp_url, args.zone, args.description))


if __name__ == "__main__":
    main()
