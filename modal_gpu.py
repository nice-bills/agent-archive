"""
GPU Modal jobs — ONE play GPU + optional batch ingest.

  modal deploy modal_gpu.py
  modal run modal_gpu.py::build_clue_packs --top 1   # batch only, manual
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
        "transformers>=5.7.0",
        "torchvision>=0.19.0",
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


def _sync_src() -> None:
    import sys

    sys.path.insert(0, "/root")


def _generate_case_on_gpu(
    image_b64: str,
    publication: str,
    date: str,
    citation_url: str,
    hint_ocr: str,
    mystery_score: float,
) -> dict:
    import base64
    import gc
    import tempfile
    from pathlib import Path

    _sync_src()
    import os

    os.environ["ARCHIVE_DETECTIVE_USE_MODEL"] = "1"
    from archive_detective.cabinet_generator import finalize_cabinet_payload
    from archive_detective.cabinet_prompts import build_cabinet_prompt
    from archive_detective.text_inference import local_chat_json, text_model_id
    from archive_detective.vision import MODEL_ID as vision_id, transcribe_image, unload_model

    hint = hint_ocr.strip()
    if len(hint) >= 20:
        raw = hint
        ocr_payload = {
            "raw_ocr": raw,
            "clean_text": raw,
            "ocr_source": "user_paste",
        }
    else:
        data = base64.b64decode(image_b64)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(data)
            img_path = tmp.name
        try:
            ocr_payload = transcribe_image(
                img_path,
                publication=publication,
                date=date,
                hint_ocr=hint_ocr,
            )
        finally:
            Path(img_path).unlink(missing_ok=True)

        raw = str(ocr_payload.get("raw_ocr") or "").strip()
        if len(raw) < 20 and hint:
            raw = hint
        if len(raw) < 20:
            raise RuntimeError("OCR produced too little text")

    unload_model()
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass

    system, user = build_cabinet_prompt(
        publication=publication,
        date=date,
        citation_url=citation_url,
        raw_ocr=raw,
        mystery_score=mystery_score,
    )
    cabinet_payload = None
    skeleton_filled: list[str] = []
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            raw_payload = local_chat_json(
                system=system,
                user=user,
                temperature=0.1 + 0.05 * attempt,
            )
            cabinet_payload, skeleton_filled = finalize_cabinet_payload(
                raw_payload,
                publication=publication,
                date=date,
                citation_url=citation_url,
                raw_ocr=raw,
            )
            break
        except Exception as exc:
            last_exc = exc
    if cabinet_payload is None:
        raise RuntimeError(f"MiniCPM cabinet JSON failed: {last_exc}") from last_exc

    return {
        "raw_ocr": raw,
        "clean_text": str(ocr_payload.get("clean_text") or raw),
        "ocr_model": vision_id,
        "cabinet_model": text_model_id(),
        "cabinet_payload": cabinet_payload,
        "skeleton_filled": skeleton_filled,
    }


@app.function(
    image=gpu_image,
    gpu="A10G",
    secrets=_hf_secrets(),
    timeout=60 * 30,
    memory=32768,
    max_containers=1,
    scaledown_window=300,
)
def generate_case_play(
    image_b64: str,
    publication: str,
    date: str,
    citation_url: str,
    hint_ocr: str,
    mystery_score: float,
) -> dict:
    """Single GPU job: MiniCPM-V OCR → unload → MiniCPM text cabinet JSON."""
    return _generate_case_on_gpu(
        image_b64, publication, date, citation_url, hint_ocr, mystery_score
    )


@app.function(
    image=gpu_image,
    gpu="A10G",
    volumes={DATA_MOUNT: vol},
    timeout=60 * 45,
    memory=16384,
    secrets=_hf_secrets(),
    max_containers=1,
)
def build_clue_packs(top: int = 5, use_model: bool = True) -> dict:
    """Batch ingest only — not used at play time."""
    _sync_src()
    from archive_detective.clue_builder import build_clue_pack_from_snippet
    from archive_detective.ingest.chronicling_america import resolve_snippet_image
    from archive_detective.ingest.ranking import rank_snippets

    raw_dir = Path(DATA_MOUNT) / "raw"
    if not (raw_dir / "manifest.json").is_file():
        fetch_fn = modal.Function.from_name(CPU_APP, "rank_snippets")
        fetch_fn.remote(target=max(top * 3, 15))

    ranked = rank_snippets(raw_dir=raw_dir)
    packs_dir = Path(DATA_MOUNT) / "clue_packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    built: list[str] = []

    if use_model:
        if not os.environ.get("HF_TOKEN"):
            raise RuntimeError("GPU clue packs need HF_TOKEN via Modal secret `huggingface`.")
        os.environ["ARCHIVE_DETECTIVE_USE_MODEL"] = "1"
        from archive_detective import vision  # noqa: F401

    for row in ranked[:top]:
        vision_payload = None
        if use_model:
            img_path = resolve_snippet_image(row, raw_dir)
            if img_path and img_path.is_file():
                try:
                    from archive_detective.vision import extract_clues_from_image

                    vision_payload = extract_clues_from_image(
                        str(img_path),
                        publication=row.get("publication", ""),
                        date=row.get("date", ""),
                        raw_ocr=row.get("raw_ocr", ""),
                    )
                except Exception as exc:
                    vision_payload = {"_error": str(exc)[:500]}

        pack = build_clue_pack_from_snippet(row, vision_payload=vision_payload)
        out_path = packs_dir / f"{pack.artifact_id}.json"
        out_path.write_text(pack.model_dump_json(indent=2) + "\n", encoding="utf-8")
        built.append(pack.artifact_id)

    vol.commit()
    return {"built": built, "dir": str(packs_dir)}


@app.local_entrypoint()
def main(top: int = 1) -> None:
    print(build_clue_packs.remote(top=top))
