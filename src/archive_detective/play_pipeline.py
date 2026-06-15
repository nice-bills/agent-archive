"""Single live-generation pipeline for gallery and upload."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from archive_detective.cabinet_generator import (
    build_case_from_payload,
    generate_cabinet_from_clipping,
)
from archive_detective.gallery import GalleryClipping
from archive_detective.hf_inference import DEFAULT_MODEL, hf_enabled
from archive_detective.modal_play import (
    cabinet_model_label,
    generate_play_modal,
    modal_play_enabled,
)
from archive_detective.models import EvidenceCase
from archive_detective.ocr_inference import ocr_for_clipping, ocr_for_upload

LiveSource = Literal["live_modal", "live"]

MODEL_REQUIRED_MSG = (
    "Gallery generation needs Modal tokens (OpenBMB MiniCPM-V + MiniCPM5-1B on GPU) "
    "or HF_TOKEN for Qwen fallback. Set MODAL_TOKEN_ID/SECRET or HF_TOKEN."
)


@dataclass(frozen=True)
class PlayInput:
    image_path: str
    publication: str
    date: str
    citation_url: str
    hint_ocr: str
    mystery_score: float


def play_backend_name() -> str:
    if modal_play_enabled():
        return "modal_openbmb"
    if hf_enabled():
        return "hosted_hf"
    return "none"


def require_live_backend() -> None:
    if play_backend_name() != "none":
        return
    raise RuntimeError(MODEL_REQUIRED_MSG)


def resolve_cabinet_model_id() -> str:
    if modal_play_enabled():
        return cabinet_model_label()
    import os

    return os.environ.get("ARCHIVE_DETECTIVE_HF_MODEL", DEFAULT_MODEL)


def _modal_meta(play: dict[str, Any], skeleton_filled: list[str] | None = None) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "ocr_source": "live_vision_modal",
        "ocr_model": play["ocr_model"],
        "source": "live_modal",
        "model_id": play["cabinet_model"],
        "cabinet_model": play["cabinet_model"],
        "stack": "openbmb",
    }
    if skeleton_filled:
        meta["skeleton_filled"] = skeleton_filled
    return meta


def _hosted_meta(ocr_meta: dict[str, Any], used_model: str, source: LiveSource) -> dict[str, Any]:
    return {
        **ocr_meta,
        "source": source,
        "model_id": used_model,
        "cabinet_model": used_model,
        "stack": "mixed",
    }


def generate_live_case(
    clipping: GalleryClipping,
    *,
    case_id: str | None = None,
) -> tuple[EvidenceCase, dict[str, Any]]:
    """One entry point for gallery + upload live generation."""
    if modal_play_enabled():
        play = generate_play_modal(
            image_path=clipping.image_path,
            publication=clipping.publication,
            date=clipping.date,
            citation_url=clipping.citation_url,
            hint_ocr=clipping.raw_ocr,
            mystery_score=clipping.mystery_score,
        )
        clipping = clipping.model_copy(update={"raw_ocr": play["raw_ocr"]})
        case = build_case_from_payload(
            play["cabinet_payload"],
            clipping=clipping,
            case_id=case_id,
        )
        meta = _modal_meta(play, play.get("skeleton_filled"))
        return case, meta

    clipping, ocr_meta = _clipping_with_live_ocr(clipping)
    case, source, used_model = generate_cabinet_from_clipping(
        clipping,
        force_live=True,
        model_id=resolve_cabinet_model_id(),
    )
    if source not in {"live", "live_modal"}:
        raise RuntimeError(f"Expected live model generation, got {source!r}")
    meta = _hosted_meta(ocr_meta, used_model, source)  # type: ignore[arg-type]
    if case_id:
        case = case.model_copy(update={"case_id": case_id})
    return case, meta


def generate_live_upload_case(
    *,
    clipping: GalleryClipping,
    case_id: str,
) -> tuple[EvidenceCase, dict[str, Any]]:
    """Upload path — same pipeline after clipping record is built."""
    if modal_play_enabled():
        return generate_live_case(clipping, case_id=case_id)

    live_ocr, ocr_meta = ocr_for_upload(
        image_path=clipping.image_path,
        raw_ocr=clipping.raw_ocr,
        publication=clipping.publication,
        date=clipping.date,
    )
    clipping = clipping.model_copy(update={"raw_ocr": live_ocr})
    case, source, used_model = generate_cabinet_from_clipping(
        clipping,
        force_live=True,
        model_id=resolve_cabinet_model_id(),
    )
    if source not in {"live", "live_modal"}:
        raise RuntimeError(f"Expected live model generation, got {source!r}")
    case = case.model_copy(update={"case_id": case_id})
    meta = _hosted_meta(ocr_meta, used_model, source)  # type: ignore[arg-type]
    return case, meta


def _clipping_with_live_ocr(
    clipping: GalleryClipping,
) -> tuple[GalleryClipping, dict[str, Any]]:
    raw_ocr, ocr_meta = ocr_for_clipping(clipping)
    return clipping.model_copy(update={"raw_ocr": raw_ocr}), ocr_meta
