"""ReID feature extractor.

Phase 1: Returns a zero-vector stub. OSNet will replace this in Phase 2
once the GPU environment and torchreid are available.
"""
from __future__ import annotations

import numpy as np

from gym_shared.logging import get_logger

log = get_logger(__name__)

_EMBEDDING_DIM = 256


class ReIDExtractor:
    """Extracts a ReID embedding from a person crop.

    Phase 1 stub — returns a zero vector so downstream consumers can
    store the field without crashing. Real OSNet embeddings added in T15b.
    """

    def __init__(self, model_path: str | None = None, device: str = "cpu") -> None:
        if model_path:
            log.warning(
                "reid_stub_active",
                message="OSNet not loaded — returning zero embeddings (Phase 1 stub)",
            )
        else:
            log.info("reid_stub_active", embedding_dim=_EMBEDDING_DIM)

    def extract(self, person_crop: np.ndarray) -> np.ndarray:
        """Return an L2-normalized zero vector (stub).

        Args:
            person_crop: HxWx3 uint8 RGB crop of a detected person.

        Returns:
            np.ndarray of shape (256,) — zero vector for Phase 1.
        """
        return np.zeros(_EMBEDDING_DIM, dtype=np.float32)
