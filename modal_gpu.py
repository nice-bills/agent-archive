"""
GPU Modal jobs — MiniCPM clue-pack generation.

  modal run modal_gpu.py::build_clue_packs --top 1
"""

from __future__ import annotations

import os
from pathlib import Path

import modal

APP_NAME = "archive-detective-gpu"
CPU_APP = "archive-detective"
ROOT = Path(__file__).resolve().parent

app = modal.App(APP_NAME)
vol = modal.Volume.from_name("archive-detective-data", create_if_missing=True)
DATA_MOUNT = "/data"

gpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "httpx>=0.28",
        "pillow>=12.2",
        "pydantic>=2.13",
        "torch>=2.4",
        "transformers>=4.48",
        "accelerate>=1.2",
        "sentencepiece>=0.2",
        "protobuf>=5.0",
    )
    .env({"ARCHIVE_DETECTIVE_USE_MODEL": "1"})
    .add_local_dir(str(ROOT / "src" / "archive_detective"), remote_path="/root/archive_detective")
)


def _hf_secrets() -> list[modal.Secret]:
    if os.environ.get("HF_TOKEN"):
        return [modal.Secret.from_local_environ(["HF_TOKEN"])]
    return [modal.Secret.from_name("huggingface")]


def _sync_src():
    import sys

    sys.path.insert(0, "/root")


@app.function(
    image=gpu_image,
    gpu="A10G",
    volumes={DATA_MOUNT: vol},
    timeout=60 * 45,
    memory=16384,
    secrets=_hf_secrets(),
)
def build_clue_packs(top: int = 5, use_model: bool = True) -> dict:
    """Build clue-pack JSON for top-ranked snippets (MiniCPM on GPU when enabled)."""
    _sync_src()
    from archive_detective.clue_builder import build_clue_pack_from_snippet
    from archive_detective.ingest.ranking import rank_snippets

    raw_dir = Path(DATA_MOUNT) / "raw"
    if not (raw_dir / "manifest.json").is_file():
        fetch_fn = modal.Function.from_name(CPU_APP, "rank_snippets")
        fetch_fn.remote(target=max(top * 3, 15))

    ranked = rank_snippets(raw_dir=raw_dir)
    packs_dir = Path(DATA_MOUNT) / "clue_packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    built: list[str] = []
    repo_root = Path("/root")

    if use_model:
        if not os.environ.get("HF_TOKEN"):
            raise RuntimeError(
                "GPU clue packs need HF_TOKEN. Run: export HF_TOKEN=hf_... "
                "or: modal secret create huggingface HF_TOKEN=hf_..."
            )
        os.environ["ARCHIVE_DETECTIVE_USE_MODEL"] = "1"
        from archive_detective import vision

    for row in ranked[:top]:
        vision_payload = None
        img = row.get("image_path")
        if use_model and img:
            full = repo_root / img
            if not full.is_file():
                full = raw_dir.parent.parent / img
            if full.is_file():
                try:
                    vision_payload = vision.extract_clues_from_image(
                        str(full),
                        publication=row.get("publication", ""),
                        date=row.get("date", ""),
                        raw_ocr=row.get("raw_ocr", ""),
                    )
                except Exception:
                    vision_payload = None

        pack = build_clue_pack_from_snippet(row, vision_payload=vision_payload)
        out_path = packs_dir / f"{pack.artifact_id}.json"
        out_path.write_text(pack.model_dump_json(indent=2) + "\n", encoding="utf-8")
        built.append(pack.artifact_id)

    vol.commit()
    return {"built": built, "dir": str(packs_dir)}


@app.local_entrypoint()
def main(top: int = 1) -> None:
    print(build_clue_packs.remote(top=top))
