#!/usr/bin/env python3
"""Stage gallery clippings: metadata + IIIF images under assets/gallery/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import httpx

from archive_detective.ingest.chronicling_america import RAW_DIR

GALLERY_DIR = ROOT / "assets" / "gallery"
META_PATH = ROOT / "data" / "gallery" / "clippings.json"
COUNT = 10


def _download(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 1024:
        return True
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "ArchiveDetective/0.1"})
            r.raise_for_status()
            dest.write_bytes(r.content)
        return dest.stat().st_size > 1024
    except (httpx.HTTPError, OSError) as exc:
        print(f"  skip download {dest.name}: {exc}")
        return False


def _headline(snippet: dict) -> str:
    pub = snippet.get("publication", "Unknown")
    date = snippet.get("date", "")
    query = snippet.get("query", "mystery")
    return f"{pub} · {date} · {query}"


def main() -> None:
    ranked_path = RAW_DIR / "ranked.json"
    if not ranked_path.is_file():
        raise SystemExit("Missing data/raw/ranked.json — run fetch first")

    ranked = json.loads(ranked_path.read_text(encoding="utf-8")).get("snippets") or []
    selected = ranked[:COUNT]
    clippings: list[dict] = []

    for row in selected:
        sid = row["snippet_id"]
        image_url = row.get("image_url")
        if not image_url:
            print(f"  skip {sid}: no image_url")
            continue
        dest = GALLERY_DIR / f"{sid}.jpg"
        if not _download(image_url, dest):
            continue
        clippings.append(
            {
                "id": sid,
                "headline": _headline(row),
                "title": row.get("title", sid),
                "date": row.get("date", ""),
                "publication": row.get("publication", "Unknown"),
                "citation_url": row.get("citation_url", ""),
                "raw_ocr": row.get("raw_ocr", ""),
                "image_path": f"assets/gallery/{sid}.jpg",
                "image_url": image_url,
                "mystery_score": row.get("mystery_score", 0.5),
                "query": row.get("query", ""),
            }
        )
        print(f"  ok {sid}")

    META_PATH.parent.mkdir(parents=True, exist_ok=True)
    META_PATH.write_text(json.dumps({"clippings": clippings}, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(clippings)} clippings -> {META_PATH}")


if __name__ == "__main__":
    main()
