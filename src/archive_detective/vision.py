"""Vision / OCR pipeline — MiniCPM-V integration stub for hackathon iteration."""

from __future__ import annotations

import os
from typing import Any

MODEL_ID = os.environ.get("ARCHIVE_DETECTIVE_MODEL", "openbmb/MiniCPM-V-4_6")


def model_enabled() -> bool:
    return os.environ.get("ARCHIVE_DETECTIVE_USE_MODEL", "").lower() in {"1", "true", "yes"}


def extract_clues_from_image(_image_path: str) -> dict[str, Any]:
    """
    Placeholder for MiniCPM-V grounded extraction.
    When ARCHIVE_DETECTIVE_USE_MODEL=1, wire HF inference here.
    """
    raise NotImplementedError(
        "Live model extraction is not wired yet. Use prebuilt clue packs in data/cases/."
    )
