#!/usr/bin/env python3
"""Visualize YOLO pose detection on a video file.

Draws bounding boxes, track IDs, and skeleton keypoints on each frame.
Writes the annotated output to a new video file.

Usage:
    python scripts/visualize_video.py input.mp4 output_annotated.mp4

    # Or show live (requires display):
    python scripts/visualize_video.py input.mp4 --show

Dependencies: pip install ultralytics opencv-python
              (already installed if you've run `uv sync`)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# COCO 17-keypoint skeleton connections
_SKELETON = [
    (0, 1), (0, 2), (1, 3), (2, 4),           # head
    (5, 6),                                     # shoulders
    (5, 7), (7, 9),                             # left arm
    (6, 8), (8, 10),                            # right arm
    (5, 11), (6, 12),                           # torso
    (11, 12),                                   # hips
    (11, 13), (13, 15),                         # left leg
    (12, 14), (14, 16),                         # right leg
]

_COLORS = [
    (255, 0, 0), (0, 255, 0), (0, 0, 255),
    (255, 165, 0), (128, 0, 128), (0, 255, 255),
]


def _color_for_track(track_id: int) -> tuple[int, int, int]:
    return _COLORS[track_id % len(_COLORS)]


def draw_skeleton(
    frame: np.ndarray,
    keypoints: np.ndarray,
    color: tuple[int, int, int],
    vis_thresh: float = 0.3,
) -> None:
    """Draw keypoint dots and skeleton lines on frame (in-place)."""
    h, w = frame.shape[:2]
    pts = []
    for kx, ky, kv in keypoints:
        px = int(kx * w) if kx <= 1.0 else int(kx)
        py = int(ky * h) if ky <= 1.0 else int(ky)
        pts.append((px, py, float(kv)))

    # Skeleton lines
    for i, j in _SKELETON:
        if i < len(pts) and j < len(pts):
            xi, yi, vi = pts[i]
            xj, yj, vj = pts[j]
            if vi > vis_thresh and vj > vis_thresh:
                cv2.line(frame, (xi, yi), (xj, yj), color, 2, cv2.LINE_AA)

    # Keypoint dots
    for px, py, pv in pts:
        if pv > vis_thresh:
            cv2.circle(frame, (px, py), 4, color, -1, cv2.LINE_AA)
            cv2.circle(frame, (px, py), 4, (255, 255, 255), 1, cv2.LINE_AA)


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize YOLO pose on a video")
    parser.add_argument("input", help="Input video file path")
    parser.add_argument("output", nargs="?", help="Output annotated video path")
    parser.add_argument("--show", action="store_true", help="Display frames live")
    parser.add_argument(
        "--model", default="yolo11n-pose.pt", help="YOLO pose model (default: yolo11n-pose.pt)"
    )
    parser.add_argument("--conf", type=float, default=0.4, help="Confidence threshold")
    args = parser.parse_args()

    from ultralytics import YOLO

    if not Path(args.input).exists():
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading model: {args.model}")
    model = YOLO(args.model)

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        print(f"Error: cannot open video: {args.input}", file=sys.stderr)
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    writer = None
    if args.output:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(args.output, fourcc, fps, (width, height))

    print(f"Input:  {args.input} ({width}x{height} @ {fps:.1f} fps, {total} frames)")
    if args.output:
        print(f"Output: {args.output}")

    frame_idx = 0
    t_start = time.monotonic()

    try:
        for result in model.track(
            source=args.input,
            conf=args.conf,
            classes=[0],   # person only
            stream=True,
            verbose=False,
        ):
            frame = result.orig_img.copy()  # BGR

            boxes = result.boxes
            kps = result.keypoints

            if boxes is not None:
                for i in range(len(boxes)):
                    track_id = int(boxes.id[i]) if boxes.id is not None else i
                    conf = float(boxes.conf[i])
                    x1, y1, x2, y2 = map(int, boxes.xyxy[i].tolist())

                    color = _color_for_track(track_id)

                    # Bounding box
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    label = f"#{track_id} {conf:.2f}"
                    cv2.putText(
                        frame, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA
                    )

                    # Skeleton
                    if kps is not None and i < len(kps.data):
                        kp_data = kps.data[i].cpu().numpy()  # (17, 3) pixel coords
                        # Convert pixel to normalized for draw_skeleton
                        kp_norm = kp_data.copy()
                        kp_norm[:, 0] /= width
                        kp_norm[:, 1] /= height
                        draw_skeleton(frame, kp_norm, color)

            # FPS overlay
            elapsed = time.monotonic() - t_start
            proc_fps = (frame_idx + 1) / elapsed if elapsed > 0 else 0
            cv2.putText(
                frame,
                f"Frame {frame_idx} | {proc_fps:.1f} fps",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )

            if writer:
                writer.write(frame)

            if args.show:
                cv2.imshow("Gym Vision", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            frame_idx += 1
            if frame_idx % 30 == 0:
                print(f"  {frame_idx}/{total} frames ({proc_fps:.1f} fps processing)")

    finally:
        cap.release()
        if writer:
            writer.release()
        if args.show:
            cv2.destroyAllWindows()

    elapsed = time.monotonic() - t_start
    print(f"\nDone. {frame_idx} frames in {elapsed:.1f}s ({frame_idx/elapsed:.1f} fps)")
    if args.output:
        print(f"Annotated video saved to: {args.output}")


if __name__ == "__main__":
    main()
