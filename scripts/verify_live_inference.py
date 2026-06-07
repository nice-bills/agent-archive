#!/usr/bin/env python3
"""Optional live HF inference check (requires HF_TOKEN)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from archive_detective.env import load_project_env
from archive_detective.gallery import load_gallery_catalog
from archive_detective.generation import generate_from_gallery
from archive_detective.hf_inference import hf_enabled, hf_health

load_project_env()


def main() -> None:
    if not hf_enabled():
        print("SKIP: HF_TOKEN not set")
        return

    if not hf_health():
        print("FAIL: HF inference health check failed")
        raise SystemExit(1)

    clippings = load_gallery_catalog()
    if not clippings:
        print("FAIL: no gallery clippings")
        raise SystemExit(1)

    case, meta = generate_from_gallery(clippings[0].id, regenerate=True)
    print(f"OK: live generation for {clippings[0].id}")
    print(f"  source={meta.get('source')} model={meta.get('model_id')}")
    print(f"  case_id={case.case_id} artifacts={len(case.artifacts)}")


if __name__ == "__main__":
    main()
