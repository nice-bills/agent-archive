"""Download IIIF images for ranked snippets missing local files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from archive_detective.ingest.chronicling_america import RAW_DIR, resolve_snippet_image


def main() -> None:
    ranked_path = RAW_DIR / "ranked.json"
    if not ranked_path.is_file():
        print("No ranked.json — run fetch first")
        return
    ranked = json.loads(ranked_path.read_text(encoding="utf-8")).get("snippets") or []
    ok = 0
    for row in ranked[:10]:
        path = resolve_snippet_image(row, RAW_DIR)
        if path:
            row["image_path"] = str(path.relative_to(RAW_DIR))
            sid = row["snippet_id"]
            snip_path = RAW_DIR / "snippets" / f"{sid}.json"
            if snip_path.is_file():
                snip_path.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
            ok += 1
            print(f"  ok {sid} -> {path.name}")
    print(f"Downloaded {ok} images")


if __name__ == "__main__":
    main()
