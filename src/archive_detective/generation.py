"""Orchestrate gallery/upload → live model → optional cache."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from archive_detective.cabinet_generator import build_heuristic_cabinet
from archive_detective.cabinet_prompts import CABINET_PROMPT_VERSION
from archive_detective.gallery import GalleryClipping, get_clipping, load_gallery_catalog
from archive_detective.generated_cache import (
    cache_path_for_clipping,
    cache_path_for_upload,
    find_cached_case_for_clipping,
    gallery_has_cached_case,
    load_cached_case,
    save_cached_case,
    stable_upload_id,
    upload_hash,
)
from archive_detective.models import EvidenceCase
from archive_detective.modal_play import modal_play_enabled
from archive_detective.play_pipeline import (
    MODEL_REQUIRED_MSG,
    generate_live_case,
    generate_live_upload_case,
    require_live_backend,
    resolve_cabinet_model_id,
)

UPLOAD_NO_OCR_SPACE_MSG = (
    "Paste OCR text from Chronicling America (or similar) before building. "
    "Image-only uploads need 3–5 minutes on Modal GPU and usually time out on this Space."
)

ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "assets" / "uploads"


def gallery_catalog() -> list[dict[str, Any]]:
    model_id = resolve_cabinet_model_id()
    return [
        {
            "id": c.id,
            "headline": c.headline or c.title,
            "date": c.date,
            "publication": c.publication,
            "mystery_score": c.mystery_score,
            "query": c.query,
            "thumb_url": f"/{c.image_path}" if c.image_path.startswith("assets/") else None,
            "has_cache": gallery_has_cached_case(c.id, model_id),
        }
        for c in load_gallery_catalog()
    ]


def _allow_heuristic() -> bool:
    return os.environ.get("ARCHIVE_DETECTIVE_ALLOW_HEURISTIC", "").lower() in {"1", "true", "yes"}


def _use_cache_reads() -> bool:
    return os.environ.get("ARCHIVE_DETECTIVE_USE_CACHE", "").lower() in {"1", "true", "yes"}


def _upload_requires_pasted_ocr() -> bool:
    """HF Space proxy often drops the client before Modal vision finishes."""
    if os.environ.get("ARCHIVE_DETECTIVE_ALLOW_IMAGE_ONLY_UPLOAD", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        return False
    return bool(os.environ.get("SPACE_ID")) and modal_play_enabled()


def _demo_pace_cache_hit() -> None:
    """Hold archivist overlay during demo capture (cache hits are otherwise instant)."""
    raw = os.environ.get("ARCHIVE_DETECTIVE_DEMO_PACER", "").strip()
    if not raw or not _use_cache_reads():
        return
    import time

    time.sleep(max(0.0, float(raw)))


def _try_heuristic_fallback(
    clipping: GalleryClipping,
    meta: dict[str, Any],
    cache_path: Path,
    exc: Exception,
) -> tuple[EvidenceCase, dict[str, Any]] | None:
    if not _allow_heuristic():
        return None
    case = build_heuristic_cabinet(clipping)
    meta["source"] = "heuristic"
    meta["live_error"] = str(exc)[:300]
    save_cached_case(cache_path, case)
    return case, meta


def generate_from_gallery(
    clipping_id: str,
    *,
    regenerate: bool = False,
) -> tuple[EvidenceCase, dict[str, Any]]:
    clipping = get_clipping(clipping_id)
    if clipping is None:
        raise ValueError(f"Unknown gallery clipping: {clipping_id}")

    model_id = resolve_cabinet_model_id()
    cache_path = cache_path_for_clipping(clipping_id, model_id)
    meta: dict[str, Any] = {
        "clipping_id": clipping_id,
        "model_id": model_id,
        "prompt_version": CABINET_PROMPT_VERSION,
        "cache_path": str(cache_path.relative_to(ROOT)),
    }

    if not regenerate:
        hit = find_cached_case_for_clipping(clipping_id, model_id)
        if hit is not None:
            cached, hit_path = hit
            meta["source"] = "cache"
            meta["cache_path"] = str(hit_path.relative_to(ROOT))
            _demo_pace_cache_hit()
            return cached, meta

    require_live_backend()
    try:
        case, live_meta = generate_live_case(clipping)
        meta.update(live_meta)
        save_cached_case(cache_path, case)
        return case, meta
    except Exception as exc:
        fallback = _try_heuristic_fallback(clipping, meta, cache_path, exc)
        if fallback:
            return fallback
        raise RuntimeError(f"Model generation failed: {exc}") from exc


def generate_from_upload(
    image_b64: str,
    *,
    title: str = "Uploaded clipping",
    raw_ocr: str = "",
    regenerate: bool = False,
) -> tuple[EvidenceCase, dict[str, Any]]:
    if not image_b64.strip():
        raise ValueError("image_b64 is required")

    raw = image_b64.strip()
    if "," in raw[:80]:
        raw = raw.split(",", 1)[1]
    image_bytes = base64.b64decode(raw)
    if len(image_bytes) < 256:
        raise ValueError("Uploaded image is too small")

    if _upload_requires_pasted_ocr() and not raw_ocr.strip():
        raise ValueError(UPLOAD_NO_OCR_SPACE_MSG)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = stable_upload_id(title, image_bytes)
    rel_path = f"assets/uploads/{upload_id}.jpg"
    dest = ROOT / rel_path
    if not dest.is_file():
        dest.write_bytes(image_bytes)

    model_id = resolve_cabinet_model_id()
    uhash = upload_hash(image_bytes, raw_ocr)
    cache_path = cache_path_for_upload(uhash, model_id)
    meta: dict[str, Any] = {
        "upload_id": upload_id,
        "model_id": model_id,
        "prompt_version": CABINET_PROMPT_VERSION,
        "cache_path": str(cache_path.relative_to(ROOT)),
    }

    if not regenerate and _use_cache_reads():
        cached = load_cached_case(cache_path)
        if cached is not None:
            meta["source"] = "cache"
            _demo_pace_cache_hit()
            return cached, meta

    clipping = GalleryClipping(
        id=upload_id,
        headline=title,
        title=title,
        date="unknown",
        publication="Uploaded clipping",
        citation_url="https://www.loc.gov/",
        raw_ocr=raw_ocr,
        image_path=rel_path,
        mystery_score=0.5,
    )
    case_id = f"generated_upload_{upload_id}"

    require_live_backend()
    try:
        case, live_meta = generate_live_upload_case(
            clipping=clipping,
            case_id=case_id,
        )
        meta.update(live_meta)
        save_cached_case(cache_path, case)
        return case, meta
    except Exception as exc:
        fallback = _try_heuristic_fallback(clipping, meta, cache_path, exc)
        if fallback:
            return fallback
        raise RuntimeError(f"Model generation failed: {exc}") from exc
