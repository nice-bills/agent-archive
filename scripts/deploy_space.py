#!/usr/bin/env python3
"""Deploy a minimal Hugging Face Space bundle (not the whole dev repo)."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from archive_detective.env import load_project_env

load_project_env()

# Only what the Gradio Space needs to run prebuilt cases.
SPACE_FILES = [
    "app.py",
    "requirements.txt",
    "README.md",
    "src/archive_detective/__init__.py",
    "src/archive_detective/api.py",
    "src/archive_detective/cabinet_generator.py",
    "src/archive_detective/cabinet_prompts.py",
    "src/archive_detective/cases.py",
    "src/archive_detective/clue_builder.py",
    "src/archive_detective/engine.py",
    "src/archive_detective/env.py",
    "src/archive_detective/evidence_engine.py",
    "src/archive_detective/gallery.py",
    "src/archive_detective/generated_cache.py",
    "src/archive_detective/generation.py",
    "src/archive_detective/hf_inference.py",
    "src/archive_detective/models.py",
    "src/archive_detective/prompts.py",
    "src/archive_detective/server_app.py",
    "src/archive_detective/static/board/index.html",
    "src/archive_detective/static/board/board.css",
    "src/archive_detective/static/board/board.js",
    "src/archive_detective/ingest/__init__.py",
    "src/archive_detective/ingest/ranking.py",
]

SPACE_README = """---
title: Archive Detective
emoji: 🕵️
colorFrom: yellow
colorTo: gray
sdk: gradio
sdk_version: "6.16.0"
app_file: app.py
pinned: false
license: mit
short_description: Micro-mysteries from public-domain news clippings
---

# Archive Detective

Play short mystery cases built from **public-domain newspaper fragments** (Chronicling America / Library of Congress).

Pick a curated case **or** generate a new Evidence Cabinet from bundled LOC clippings.

Set `HF_TOKEN` as a Space secret for live hosted inference; cached cabinets work offline.
"""


def _stage_bundle(staging: Path) -> None:
    for rel in SPACE_FILES:
        src = ROOT / rel
        if not src.is_file():
            raise SystemExit(f"Missing Space file: {rel}")
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    # Cases + assets only (no raw ingest, scripts, or Modal code).
    for case in (ROOT / "data" / "cases").glob("*.json"):
        dest = staging / "data" / "cases" / case.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(case, dest)

    asset_root = ROOT / "assets"
    if asset_root.is_dir():
        for asset in asset_root.rglob("*"):
            if not asset.is_file():
                continue
            if asset.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                continue
            rel = asset.relative_to(asset_root)
            dest = staging / "assets" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset, dest)

    gallery_meta = ROOT / "data" / "gallery" / "clippings.json"
    if gallery_meta.is_file():
        dest = staging / "data" / "gallery" / "clippings.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gallery_meta, dest)

    gen_dir = ROOT / "data" / "generated_cases"
    if gen_dir.is_dir():
        for case in gen_dir.glob("*.json"):
            dest = staging / "data" / "generated_cases" / case.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(case, dest)

    (staging / "README.md").write_text(SPACE_README, encoding="utf-8")


def main() -> None:
    import os

    from huggingface_hub import HfApi

    parser = argparse.ArgumentParser(description="Deploy minimal HF Space bundle")
    parser.add_argument(
        "--repo",
        default=None,
        help="Target repo id (default: <hf-user>/archive-detective)",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help="Make the Space public (default: private)",
    )
    parser.add_argument(
        "--confirm-local",
        action="store_true",
        help="Required: run scripts/verify_local.py first",
    )
    parser.add_argument(
        "--delete-remote",
        action="store_true",
        help="Delete the Space repo entirely instead of uploading",
    )
    args = parser.parse_args()

    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN missing — set in .env")

    api = HfApi(token=token)
    user = api.whoami()["name"]
    repo_id = args.repo or f"{user}/archive-detective"

    if not args.delete_remote and not args.confirm_local:
        raise SystemExit(
            "Refusing to deploy without --confirm-local.\n"
            "Run: uv run python scripts/verify_local.py && "
            "uv run python scripts/deploy_space.py --confirm-local"
        )

    if args.delete_remote:
        api.delete_repo(repo_id, repo_type="space")
        print(f"Deleted https://huggingface.co/spaces/{repo_id}")
        return

    with tempfile.TemporaryDirectory() as tmp:
        staging = Path(tmp) / "space"
        staging.mkdir()
        _stage_bundle(staging)
        api.create_repo(
            repo_id,
            repo_type="space",
            space_sdk="gradio",
            exist_ok=True,
            private=not args.public,
        )
        if not args.public:
            api.update_repo_settings(repo_id, private=True, repo_type="space")
        api.upload_folder(
            folder_path=str(staging),
            repo_id=repo_id,
            repo_type="space",
            delete_patterns=["**/*"],
            commit_message="Deploy minimal Gradio Space bundle",
        )

    visibility = "public" if args.public else "private"
    print(f"Deployed ({visibility}): https://huggingface.co/spaces/{repo_id}")


if __name__ == "__main__":
    main()
