#!/usr/bin/env python3
"""Register a gym member in the PostgreSQL database.

Usage:
    # Register with face photos for biometric identification:
    python scripts/register_person.py \
        --name "John Smith" \
        --goals "strength,muscle_gain" \
        --injury-notes "left knee strain" \
        --photos-dir ~/face_photos/john

    # Register without face photos (anonymous/QR-only mode):
    python scripts/register_person.py \
        --name "Jane Doe" \
        --goals "weight_loss,endurance" \
        --skip-face

The script:
  1. Creates a Person record in the DB
  2. Optionally extracts an ArcFace 512-d face embedding from provided photos
  3. Generates a QR code PNG (saved to output/person_<id>_qr.png)
     — scan this in the mobile app to link a track to this person
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from pathlib import Path

from gym_shared.db.models import Person
from gym_shared.db.session import get_db
from gym_shared.logging import configure_logging, get_logger
from gym_shared.settings import settings

configure_logging(settings.log_format, settings.log_level)
log = get_logger(__name__)


def extract_face_embedding(photos_dir: Path) -> list[float]:
    """Extract ArcFace 512-d embedding from photos in a directory.

    Averages embeddings across all face photos for a robust representation.
    Raises RuntimeError if InsightFace is not installed or no faces found.
    """
    try:
        import insightface
        import numpy as np
    except ImportError:
        raise RuntimeError(
            "InsightFace not installed. Run: pip install insightface onnxruntime\n"
            "Or use --skip-face to register without face enrollment."
        )

    app = insightface.app.FaceAnalysis(providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1)  # -1 = CPU

    import cv2

    photo_paths = list(photos_dir.glob("*.jpg")) + list(photos_dir.glob("*.png"))
    if not photo_paths:
        raise RuntimeError(f"No .jpg or .png images found in {photos_dir}")

    embeddings = []
    for path in photo_paths:
        img = cv2.imread(str(path))
        if img is None:
            log.warning("could_not_read_image", path=str(path))
            continue
        faces = app.get(img)
        if not faces:
            log.warning("no_face_detected", path=str(path))
            continue
        # Use the largest face in the photo
        face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        embeddings.append(face.normed_embedding.tolist())

    if not embeddings:
        raise RuntimeError(
            f"No faces detected in any of the {len(photo_paths)} photos in {photos_dir}"
        )

    # Average embeddings and L2-normalize
    avg = np.mean(embeddings, axis=0)
    avg = avg / np.linalg.norm(avg)
    log.info("face_embedding_extracted", photo_count=len(embeddings))
    return avg.tolist()


def generate_qr_code(person_id: uuid.UUID, output_dir: Path) -> Path:
    """Generate a QR code encoding the person's UUID. Returns output path."""
    try:
        import qrcode
    except ImportError:
        raise RuntimeError(
            "qrcode not installed. Run: pip install qrcode[pil]\n"
            "Or skip QR generation and note the person ID manually."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"person_{person_id}_qr.png"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(str(person_id))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(str(output_path))
    return output_path


async def register(
    name: str,
    goals: list[str],
    injury_notes: str | None,
    face_embedding: list[float] | None,
) -> uuid.UUID:
    async with get_db() as db:
        person = Person(
            display_name=name,
            goals=goals,
            injury_notes=injury_notes,
            face_embedding=face_embedding,
        )
        db.add(person)
        await db.flush()
        person_id = person.id
        log.info("person_registered", person_id=str(person_id), name=name)
        return person_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Register a gym member")
    parser.add_argument("--name", required=True, help="Full name of the member")
    parser.add_argument(
        "--goals",
        default="",
        help="Comma-separated goals (e.g. 'strength,weight_loss,endurance')",
    )
    parser.add_argument("--injury-notes", default=None, help="Any injury or limitation notes")
    parser.add_argument(
        "--photos-dir",
        type=Path,
        default=None,
        help="Directory of 1–10 face photos (.jpg/.png) for biometric enrollment",
    )
    parser.add_argument(
        "--skip-face",
        action="store_true",
        help="Skip face enrollment (QR code / manual ID only)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory to save the generated QR code (default: output/)",
    )
    args = parser.parse_args()

    if not args.skip_face and args.photos_dir is None:
        parser.error("Provide --photos-dir <path> or --skip-face")

    # Parse goals
    goals = [g.strip() for g in args.goals.split(",") if g.strip()] if args.goals else []

    # Extract face embedding if photos provided
    face_embedding: list[float] | None = None
    if not args.skip_face:
        print(f"Extracting face embedding from photos in {args.photos_dir}...")
        try:
            face_embedding = extract_face_embedding(args.photos_dir)
            print(f"  ✓ Extracted embedding from photos")
        except RuntimeError as e:
            print(f"  ✗ Face extraction failed: {e}", file=sys.stderr)
            sys.exit(1)

    # Register in DB
    print(f"Registering '{args.name}' in database...")
    person_id = asyncio.run(
        register(args.name, goals, args.injury_notes, face_embedding)
    )
    print(f"  ✓ Person created: {person_id}")

    # Generate QR code
    print(f"Generating QR code...")
    try:
        qr_path = generate_qr_code(person_id, args.output_dir)
        print(f"  ✓ QR code saved: {qr_path}")
    except RuntimeError as e:
        print(f"  ✗ QR generation failed: {e}", file=sys.stderr)
        print(f"  Person ID to note manually: {person_id}")

    print()
    print("Registration complete!")
    print(f"  Name:     {args.name}")
    print(f"  Goals:    {', '.join(goals) if goals else '(none set)'}")
    print(f"  Face:     {'enrolled' if face_embedding else 'skipped — QR-only mode'}")
    print(f"  ID:       {person_id}")
    print()
    print("Next steps:")
    print("  1. Print or share the QR code PNG with the member")
    print("  2. Member scans QR code in the Smart Gym mobile app to link their session")
    if not face_embedding:
        print("  3. To add face enrollment later, re-run with --photos-dir")


if __name__ == "__main__":
    main()
