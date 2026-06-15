"""OCR fallback when Modal play path is off — local MiniCPM-V or HF refine."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from archive_detective.gallery import GalleryClipping
from archive_detective.hf_inference import DEFAULT_MODEL, hf_enabled, hosted_chat_json
from archive_detective.ocr_prompts import build_ocr_refine_prompt

ROOT = Path(__file__).resolve().parents[2]


def vision_model_id() -> str:
    return os.environ.get("ARCHIVE_DETECTIVE_MODEL", "openbmb/MiniCPM-V-4.6")


def vision_enabled() -> bool:
    return os.environ.get("ARCHIVE_DETECTIVE_USE_MODEL", "").lower() in {"1", "true", "yes"}


def _allow_bundled_ocr() -> bool:
    return os.environ.get("ARCHIVE_DETECTIVE_ALLOW_BUNDLED_OCR", "").lower() in {"1", "true", "yes"}


def refine_ocr_hf(
    *,
    raw_ocr: str,
    publication: str = "Unknown",
    date: str = "unknown",
    model_id: str | None = None,
) -> dict[str, Any]:
    if not raw_ocr.strip():
        raise ValueError("raw_ocr is empty")
    if not hf_enabled():
        raise RuntimeError("HF_TOKEN required for hosted OCR refine")
    model = model_id or os.environ.get("ARCHIVE_DETECTIVE_HF_OCR_MODEL", DEFAULT_MODEL)
    system, user = build_ocr_refine_prompt(
        publication=publication,
        date=date,
        raw_ocr=raw_ocr,
    )
    payload = hosted_chat_json(system=system, user=user, model=model, max_tokens=2048)
    text = str(payload.get("raw_ocr") or payload.get("clean_text") or "").strip()
    if len(text) < 20:
        raise RuntimeError("OCR refine model returned too little text")
    return {
        "raw_ocr": text,
        "clean_text": str(payload.get("clean_text") or text).strip(),
        "ocr_source": "live_refine",
        "ocr_model": model,
    }


def ocr_from_image_local(
    image_path: str,
    *,
    publication: str,
    date: str,
    hint_ocr: str = "",
) -> dict[str, Any]:
    if not vision_enabled():
        raise RuntimeError(
            "Image OCR requires ARCHIVE_DETECTIVE_USE_MODEL=1 and uv sync --extra model"
        )
    from archive_detective.vision import transcribe_image

    path = ROOT / image_path if not Path(image_path).is_absolute() else Path(image_path)
    payload = transcribe_image(
        str(path),
        publication=publication,
        date=date,
        hint_ocr=hint_ocr,
    )
    text = str(payload.get("raw_ocr") or payload.get("clean_text") or "").strip()
    if len(text) < 20:
        raise RuntimeError("Vision model returned too little text")
    return {
        "raw_ocr": text,
        "clean_text": text,
        "ocr_source": "live_vision",
        "ocr_model": vision_model_id(),
        "vision_payload": payload,
    }


def ocr_for_clipping(clipping: GalleryClipping) -> tuple[str, dict[str, Any]]:
    """HF/local fallback only — play path uses modal_play.generate_play_modal."""
    meta: dict[str, Any] = {}

    if vision_enabled() and clipping.image_path:
        try:
            result = ocr_from_image_local(
                clipping.image_path,
                publication=clipping.publication,
                date=clipping.date,
                hint_ocr=clipping.raw_ocr,
            )
            return result["raw_ocr"], result
        except Exception as exc:
            meta["vision_error"] = str(exc)[:300]

    if clipping.raw_ocr.strip() and hf_enabled():
        try:
            result = refine_ocr_hf(
                raw_ocr=clipping.raw_ocr,
                publication=clipping.publication,
                date=clipping.date,
            )
            if meta:
                result["vision_error"] = meta.get("vision_error")
            return result["raw_ocr"], result
        except Exception as exc:
            meta["refine_error"] = str(exc)[:300]

    if _allow_bundled_ocr() and clipping.raw_ocr.strip():
        return clipping.raw_ocr, {
            "ocr_source": "bundled_loc",
            "ocr_model": None,
            **meta,
        }

    detail = meta.get("refine_error") or meta.get("vision_error") or "no OCR path available"
    raise RuntimeError(f"Live OCR failed: {detail}")


def ocr_for_upload(
    *,
    image_path: str,
    raw_ocr: str,
    publication: str,
    date: str,
) -> tuple[str, dict[str, Any]]:
    seed = raw_ocr.strip()
    if not seed and image_path:
        result = ocr_from_image_local(image_path, publication=publication, date=date)
        return result["raw_ocr"], result
    if not seed:
        raise RuntimeError("Upload needs pasted OCR or ARCHIVE_DETECTIVE_USE_MODEL=1")
    if hf_enabled():
        result = refine_ocr_hf(raw_ocr=seed, publication=publication, date=date)
        return result["raw_ocr"], result
    if _allow_bundled_ocr():
        return seed, {"ocr_source": "user_paste", "ocr_model": None}
    raise RuntimeError("Live OCR refine failed — set HF_TOKEN")
