"""Curated clipping gallery for model-powered case generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
GALLERY_META = ROOT / "data" / "gallery" / "clippings.json"


class GalleryClipping(BaseModel):
    id: str
    headline: str = ""
    title: str = ""
    date: str = ""
    publication: str = "Unknown"
    citation_url: str = ""
    raw_ocr: str = ""
    image_path: str = ""
    image_url: str = ""
    mystery_score: float = 0.5
    query: str = ""

    def to_snippet_dict(self) -> dict[str, Any]:
        return {
            "snippet_id": self.id,
            "citation_url": self.citation_url,
            "date": self.date,
            "publication": self.publication,
            "title": self.title,
            "raw_ocr": self.raw_ocr,
            "image_path": self.image_path,
            "image_url": self.image_url,
            "query": self.query,
            "mystery_score": self.mystery_score,
        }


def load_gallery_catalog() -> list[GalleryClipping]:
    if not GALLERY_META.is_file():
        return []
    data = json.loads(GALLERY_META.read_text(encoding="utf-8"))
    return [GalleryClipping.model_validate(row) for row in data.get("clippings") or []]


def get_clipping(clipping_id: str) -> GalleryClipping | None:
    return next((c for c in load_gallery_catalog() if c.id == clipping_id), None)


def clipping_to_catalog_dict(clipping: GalleryClipping) -> dict[str, Any]:
    return {
        "id": clipping.id,
        "headline": clipping.headline or clipping.title,
        "date": clipping.date,
        "publication": clipping.publication,
        "mystery_score": clipping.mystery_score,
        "thumb_url": f"/{clipping.image_path}" if clipping.image_path.startswith("assets/") else None,
        "query": clipping.query,
    }
