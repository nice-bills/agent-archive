"""Orchestrate gallery/upload → cache → Evidence Cabinet session."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

from archive_detective.cabinet_generator import (
    GenerationSource,
    build_heuristic_cabinet,
    generate_cabinet_from_clipping,
    generate_cabinet_from_upload,
)
from archive_detective.cabinet_prompts import CABINET_PROMPT_VERSION
from archive_detective.gallery import GalleryClipping, get_clipping, load_gallery_catalog
from archive_detective.generated_cache import (
    cache_path_for_clipping,
    cache_path_for_upload,
    load_cached_case,
    save_cached_case,
    stable_upload_id,
    upload_hash,
)
from archive_detective.hf_inference import DEFAULT_MODEL, hf_enabled
from archive_detective.models import EvidenceCase

ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = ROOT / "assets" / "uploads"


def gallery_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": c.id,
            "headline": c.headline or c.title,
            "date": c.date,
            "publication": c.publication,
            "mystery_score": c.mystery_score,
            "query": c.query,
            "thumb_url": f"/{c.image_path}" if c.image_path.startswith("assets/") else None,
        }
        for c in load_gallery_catalog()
    ]


def _resolve_model_id() -> str:
    return os.environ.get("ARCHIVE_DETECTIVE_HF_MODEL", DEFAULT_MODEL)


def _prefer_live() -> bool:
    return os.environ.get("ARCHIVE_DETECTIVE_PREFER_LIVE", "").lower() in {"1", "true", "yes"}


def generate_from_gallery(
    clipping_id: str,
    *,
    regenerate: bool = False,
) -> tuple[EvidenceCase, dict[str, Any]]:
    clipping = get_clipping(clipping_id)
    if clipping is None:
        raise ValueError(f"Unknown gallery clipping: {clipping_id}")

    model_id = _resolve_model_id()
    cache_path = cache_path_for_clipping(clipping_id, model_id)
    meta: dict[str, Any] = {
        "clipping_id": clipping_id,
        "model_id": model_id,
        "prompt_version": CABINET_PROMPT_VERSION,
        "cache_path": str(cache_path.relative_to(ROOT)),
    }

    if not regenerate:
        cached = load_cached_case(cache_path)
        if cached is not None:
            meta["source"] = "cache"
            return cached, meta

    if hf_enabled() and (regenerate or _prefer_live()):
        try:
            case, source, used_model = generate_cabinet_from_clipping(
                clipping,
                force_live=True,
                model_id=model_id,
            )
            meta["model_id"] = used_model
            meta["source"] = source
            save_cached_case(cache_path, case)
            return case, meta
        except Exception as exc:
            cached = load_cached_case(cache_path)
            if cached is not None:
                meta["source"] = "cache"
                meta["live_error"] = str(exc)[:300]
                return cached, meta
            meta["live_error"] = str(exc)[:300]

    case = build_heuristic_cabinet(clipping)
    meta["source"] = "fallback" if meta.get("live_error") else "heuristic"
    save_cached_case(cache_path, case)
    return case, meta


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

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = stable_upload_id(title, image_bytes)
    rel_path = f"assets/uploads/{upload_id}.jpg"
    dest = ROOT / rel_path
    if not dest.is_file():
        dest.write_bytes(image_bytes)

    if not raw_ocr.strip():
        raw_ocr = "(no OCR provided — model reads from image metadata only)"

    model_id = _resolve_model_id()
    uhash = upload_hash(image_bytes, raw_ocr)
    cache_path = cache_path_for_upload(uhash, model_id)
    meta: dict[str, Any] = {
        "upload_id": upload_id,
        "model_id": model_id,
        "prompt_version": CABINET_PROMPT_VERSION,
        "cache_path": str(cache_path.relative_to(ROOT)),
    }

    if not regenerate:
        cached = load_cached_case(cache_path)
        if cached is not None:
            meta["source"] = "cache"
            return cached, meta

    if hf_enabled() and (regenerate or _prefer_live()):
        try:
            case, source, used_model = generate_cabinet_from_upload(
                title=title,
                raw_ocr=raw_ocr,
                image_path=rel_path,
                force_live=True,
                model_id=model_id,
            )
            meta["model_id"] = used_model
            meta["source"] = source
            save_cached_case(cache_path, case)
            return case, meta
        except Exception as exc:
            cached = load_cached_case(cache_path)
            if cached is not None:
                meta["source"] = "cache"
                meta["live_error"] = str(exc)[:300]
                return cached, meta
            meta["live_error"] = str(exc)[:300]

    clipping = GalleryClipping(
        id=upload_id,
        headline=title,
        title=title,
        raw_ocr=raw_ocr,
        image_path=rel_path,
        image_url="",
    )
    case = build_heuristic_cabinet(clipping)
    meta["source"] = "fallback" if meta.get("live_error") else "heuristic"
    save_cached_case(cache_path, case)
    return case, meta
