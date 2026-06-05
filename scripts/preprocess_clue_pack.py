#!/usr/bin/env python3
"""Validate or normalize clue-pack JSON (Pydantic). For generation, use clue_builder or Modal."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from archive_detective.models import CluePack


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate or emit a clue-pack JSON file.")
    parser.add_argument("input", type=Path, help="Path to clue-pack JSON")
    parser.add_argument("--out", type=Path, help="Optional output path")
    args = parser.parse_args()
    pack = CluePack.model_validate_json(args.input.read_text(encoding="utf-8"))
    payload = pack.model_dump_json(indent=2)
    if args.out:
        args.out.write_text(payload + "\n", encoding="utf-8")
        print(f"Wrote {args.out}")
    else:
        print(json.dumps(json.loads(payload), indent=2))


if __name__ == "__main__":
    main()
