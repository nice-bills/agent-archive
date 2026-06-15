"""Disk cache for model-generated Evidence Cabinet cases."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from archive_detective.cabinet_prompts import CABINET_PROMPT_VERSION
from archive_detective.models import EvidenceCase

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "generated_cases"
DEFAULT_MODEL = "heuristic"


def _slug(text: str, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:max_len] or "upload"


def cache_key(*, clipping_id: str, model_id: str, prompt_version: str = CABINET_PROMPT_VERSION) -> str:
    raw = f"{clipping_id}|{model_id}|{prompt_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def cache_path_for_clipping(clipping_id: str, model_id: str) -> Path:
    key = cache_key(clipping_id=clipping_id, model_id=model_id)
    return CACHE_DIR / f"{clipping_id}_{key}.json"


def cache_path_for_upload(upload_hash: str, model_id: str) -> Path:
    key = cache_key(clipping_id=upload_hash, model_id=model_id)
    return CACHE_DIR / f"upload_{upload_hash[:12]}_{key}.json"


def load_cached_case(path: Path) -> EvidenceCase | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return EvidenceCase.model_validate(data)
    except (json.JSONDecodeError, ValueError):
        return None


def find_cached_case_for_clipping(
    clipping_id: str,
    model_id: str,
) -> tuple[EvidenceCase, Path] | None:
    """Exact model match first, then any pre-generated JSON for this clipping."""
    exact = cache_path_for_clipping(clipping_id, model_id)
    case = load_cached_case(exact)
    if case is not None:
        return case, exact

    matches = sorted(
        CACHE_DIR.glob(f"{clipping_id}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in matches:
        case = load_cached_case(path)
        if case is not None:
            return case, path
    return None


def gallery_has_cached_case(clipping_id: str, model_id: str) -> bool:
    return find_cached_case_for_clipping(clipping_id, model_id) is not None


def save_cached_case(path: Path, case: EvidenceCase) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(case.model_dump_json(indent=2) + "\n", encoding="utf-8")


def list_cached_cases() -> list[Path]:
    if not CACHE_DIR.is_dir():
        return []
    return sorted(CACHE_DIR.glob("*.json"))


def upload_hash(image_bytes: bytes, raw_ocr: str = "") -> str:
    h = hashlib.sha256()
    h.update(image_bytes)
    h.update(raw_ocr.encode("utf-8"))
    return h.hexdigest()


def stable_upload_id(title: str, image_bytes: bytes) -> str:
    return _slug(title) + "_" + upload_hash(image_bytes)[:10]
