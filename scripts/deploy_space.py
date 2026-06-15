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
    "src/archive_detective/cabinet_skeleton.py",
    "src/archive_detective/cabinet_prompts.py",
    "src/archive_detective/cases.py",
    "src/archive_detective/clue_builder.py",
    "src/archive_detective/engine.py",
    "src/archive_detective/env.py",
    "src/archive_detective/evidence_engine.py",
    "src/archive_detective/gallery.py",
    "src/archive_detective/generated_cache.py",
    "src/archive_detective/generation.py",
    "src/archive_detective/play_pipeline.py",
    "src/archive_detective/hf_inference.py",
    "src/archive_detective/modal_play.py",
    "src/archive_detective/text_inference.py",
    "src/archive_detective/vision.py",
    "src/archive_detective/ocr_inference.py",
    "src/archive_detective/ocr_prompts.py",
    "src/archive_detective/models.py",
    "src/archive_detective/prompts.py",
    "src/archive_detective/server_app.py",
    "src/archive_detective/static_files.py",
    "src/archive_detective/static/board/index.html",
    "src/archive_detective/static/board/board.css",
    "src/archive_detective/static/board/board.js",
    "src/archive_detective/static/board/api.js",
    "src/archive_detective/static/board/util.js",
    "src/archive_detective/static/board/state.js",
    "src/archive_detective/static/board/render.js",
    "src/archive_detective/static/board/scene.css",
    "src/archive_detective/static/board/tokens.css",
    "src/archive_detective/static/board/desk.css",
    "src/archive_detective/static/board/cabinet.css",
    "src/archive_detective/static/board/beat.css",
    "src/archive_detective/static/board/shared.css",
    "src/archive_detective/static/board/landing.css",
    "src/archive_detective/static/board/overlay.css",
    "src/archive_detective/static/board/motion.css",
    "src/archive_detective/ingest/__init__.py",
    "src/archive_detective/ingest/chronicling_america.py",
    "src/archive_detective/ingest/ranking.py",
]

# Hackathon submission Space (Build Small org). Override with --repo or personal default.
DEFAULT_SPACE_REPO = "build-small-hackathon/archive-detective-nice-bill"

GITHUB_REPO_URL = "https://github.com/nice-bills/agent-archive"
SPACE_REPO_URL = (
    "https://huggingface.co/spaces/build-small-hackathon/archive-detective-nice-bill"
)
AGENT_TRACE_URL = (
    "https://huggingface.co/datasets/nice-bill/archive-detective-agent-trace"
)

SPACE_README = f"""---
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
tags:
  - thousand-token-wood
  - off-brand
  - field-notes
  - sharing-is-caring
  - track:wood
  - sponsor:openbmb
  - sponsor:modal
  - achievement:offbrand
  - achievement:sharing
  - achievement:fieldnotes
models:
  - openbmb/MiniCPM-V-4.6
  - openbmb/MiniCPM5-1B
datasets:
  - nice-bill/archive-detective-agent-trace
---

# Archive Detective

Play short mystery cases built from **public-domain newspaper fragments** (Chronicling America / Library of Congress).

Pick a curated case **or** generate a new Evidence Cabinet from bundled LOC clippings.

**GitHub:** [nice-bills/agent-archive]({GITHUB_REPO_URL})

**Live Space:** [build-small-hackathon/archive-detective-nice-bill]({SPACE_REPO_URL})

**Agent trace:** [nice-bill/archive-detective-agent-trace]({AGENT_TRACE_URL})

**Demo video:** [YouTube](https://youtu.be/ADowU5BB5Wc)

**Social post:** [X](https://x.com/willIsbillls/status/2066558882026082335?s=20)

**Gallery polaroids:** pre-built cabinets in `data/generated_cases/` open instantly (no Modal wait). Use **Regenerate** for a fresh OpenBMB GPU run.

**Live path (OpenBMB):** one Modal GPU job per regenerate — MiniCPM-V-4.6 OCR → MiniCPM5-1B cabinet JSON.

**Hackathon:** Adventure in Thousand Token Wood · **Models:** [MiniCPM-V-4.6](https://huggingface.co/openbmb/MiniCPM-V-4.6) (OCR) + [MiniCPM5-1B](https://huggingface.co/openbmb/MiniCPM5-1B) (cabinet JSON) · **Infra:** Modal (`generate_case_play`, one A10G job per pick)

**Field notes:** [docs/artifacts/field-notes.html]({GITHUB_REPO_URL}/blob/main/docs/artifacts/field-notes.html) on GitHub (publish as HF blog post for judges if preferred)

Space secrets:
- `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET` — required for live generation
- `HF_TOKEN` — Modal weight download + deploy
- `ARCHIVE_DETECTIVE_MODAL_PLAY=auto`

Deploy GPU fn first: `./scripts/deploy_modal_gpu.sh` (from the GitHub repo)
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
        help=(
            "Target repo id "
            f"(default: {DEFAULT_SPACE_REPO})"
        ),
    )
    parser.add_argument(
        "--public",
        action="store_true",
        default=None,
        help="Make the Space public",
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="Make the Space private (overrides hackathon default)",
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
    repo_id = args.repo or DEFAULT_SPACE_REPO

    if args.public and args.private:
        raise SystemExit("Cannot pass both --public and --private")
    if args.public:
        public = True
    elif args.private:
        public = False
    else:
        public = "build-small-hackathon/" in repo_id

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
            private=not public,
        )
        api.update_repo_settings(repo_id, private=not public, repo_type="space")
        api.upload_folder(
            folder_path=str(staging),
            repo_id=repo_id,
            repo_type="space",
            delete_patterns=["**/*"],
            commit_message="Deploy minimal Gradio Space bundle",
        )

    visibility = "public" if public else "private"
    print(f"Deployed ({visibility}): https://huggingface.co/spaces/{repo_id}")


if __name__ == "__main__":
    main()
