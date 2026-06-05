#!/usr/bin/env python3
"""Fetch real Chronicling America snippets via Library of Congress search API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from archive_detective.ingest.chronicling_america import RAW_DIR, fetch_snippets
from archive_detective.ingest.ranking import rank_snippets


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest LOC newspaper page snippets.")
    parser.add_argument("--target", type=int, default=15, help="Number of snippets to save")
    parser.add_argument("--per-query", type=int, default=5, help="Results per search query")
    parser.add_argument("--no-images", action="store_true", help="Skip IIIF image download")
    parser.add_argument("--rank", action="store_true", help="Run heuristic ranking after fetch")
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Extra search query (repeatable)",
    )
    args = parser.parse_args()

    snippets = fetch_snippets(
        queries=args.queries,
        target=args.target,
        per_query=args.per_query,
        download_images=not args.no_images,
    )
    print(f"Saved {len(snippets)} snippets under {RAW_DIR}")

    if args.rank:
        ranked = rank_snippets()
        print(f"Ranked {len(ranked)} snippets → {RAW_DIR / 'ranked.json'}")
        for row in ranked[:5]:
            print(
                f"  {row['mystery_score']:.2f}  {row['date']}  "
                f"{row.get('publication', '')[:40]}"
            )


if __name__ == "__main__":
    main()
