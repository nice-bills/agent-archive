"""Single Modal GPU call for OpenBMB play path."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MODAL_APP = os.environ.get("ARCHIVE_DETECTIVE_MODAL_APP", "archive-detective-gpu")
MODAL_FN = os.environ.get("ARCHIVE_DETECTIVE_MODAL_PLAY_FN", "generate_case_play")


def modal_credentials_configured() -> bool:
    if os.environ.get("MODAL_TOKEN_ID") and os.environ.get("MODAL_TOKEN_SECRET"):
        return True
    return Path.home().joinpath(".modal.toml").is_file()


def modal_play_enabled() -> bool:
    flag = os.environ.get("ARCHIVE_DETECTIVE_MODAL_PLAY", "auto").lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    if flag in {"1", "true", "yes", "on"}:
        return modal_credentials_configured()
    return modal_credentials_configured()


def cabinet_model_label() -> str:
    from archive_detective.text_inference import text_model_id

    return text_model_id()


def vision_model_label() -> str:
    try:
        from archive_detective.vision import MODEL_ID

        return MODEL_ID
    except ImportError:
        return os.environ.get("ARCHIVE_DETECTIVE_MODEL", "openbmb/MiniCPM-V-4.6")


def generate_play_modal(
    *,
    image_path: str,
    publication: str,
    date: str,
    citation_url: str,
    hint_ocr: str,
    mystery_score: float,
) -> dict[str, Any]:
    if not modal_play_enabled():
        raise RuntimeError(
            "Modal play disabled. Set ARCHIVE_DETECTIVE_MODAL_PLAY=1 and run modal token new."
        )
    try:
        import modal
    except ImportError as exc:
        raise RuntimeError("Modal SDK not installed — uv sync --extra modal") from exc

    path = Path(image_path)
    if not path.is_absolute():
        path = ROOT / image_path
    if not path.is_file():
        raise FileNotFoundError(image_path)

    image_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    fn = modal.Function.from_name(MODAL_APP, MODAL_FN)
    wait_s = float(os.environ.get("ARCHIVE_DETECTIVE_MODAL_PLAY_TIMEOUT", "1800"))
    call = fn.spawn(
        image_b64=image_b64,
        publication=publication,
        date=date,
        citation_url=citation_url,
        hint_ocr=hint_ocr,
        mystery_score=mystery_score,
    )
    return call.get(timeout=wait_s)
