#!/usr/bin/env python3
"""Pre-build cached Evidence Cabinet cases for all gallery clippings."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from archive_detective.env import load_project_env
from archive_detective.gallery import load_gallery_catalog
from archive_detective.generation import generate_from_gallery

load_project_env()


def main() -> None:
    clippings = load_gallery_catalog()
    if not clippings:
        raise SystemExit("No gallery clippings — run scripts/build_gallery.py first")

    for clipping in clippings:
        case, meta = generate_from_gallery(clipping.id, regenerate=False)
        print(f"  {clipping.id}: {meta.get('source')} -> {case.case_id}")

    print(f"Cached {len(clippings)} generated cases")


if __name__ == "__main__":
    main()
