"""Vision / OCR pipeline — MiniCPM-V-4_6 with heuristic fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from archive_detective.clue_builder import parse_vision_json
from archive_detective.env import load_project_env
from archive_detective.prompts import build_extraction_prompt

load_project_env()

MODEL_ID = os.environ.get("ARCHIVE_DETECTIVE_MODEL", "openbmb/MiniCPM-V-4_6")


def _hf_token() -> str | None:
    return os.environ.get("HF_TOKEN") or None


def _load_model():
    import torch
    from transformers import AutoModel, AutoTokenizer

    token = _hf_token()
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID, trust_remote_code=True, token=token
    )
    model = AutoModel.from_pretrained(
        MODEL_ID,
        trust_remote_code=True,
        attn_implementation="sdpa",
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        token=token,
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.eval().to(device)
    return model, tokenizer, device


def model_enabled() -> bool:
    return os.environ.get("ARCHIVE_DETECTIVE_USE_MODEL", "").lower() in {"1", "true", "yes"}


def _run_minicpm_chat(
    model: Any,
    tokenizer: Any,
    device: str,
    image_path: str,
    system: str,
    user: str,
) -> str:
    from PIL import Image

    image = Image.open(image_path).convert("RGB")
    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": [image, user]},
    ]
    response = model.chat(
        image=None,
        msgs=msgs,
        tokenizer=tokenizer,
        sampling=False,
        max_new_tokens=1024,
    )
    if isinstance(response, tuple):
        response = response[0]
    return str(response)


def extract_clues_from_image(
    image_path: str,
    *,
    publication: str = "Unknown",
    date: str = "unknown",
    raw_ocr: str = "",
) -> dict[str, Any]:
    """
    Structured clue extraction from a clipping image.
    Set ARCHIVE_DETECTIVE_USE_MODEL=1 for live MiniCPM-V (GPU recommended).
    """
    system, user = build_extraction_prompt(
        publication=publication,
        date=date,
        raw_ocr=raw_ocr or "(no OCR provided)",
    )

    if not model_enabled():
        raise RuntimeError(
            "Live model disabled. Set ARCHIVE_DETECTIVE_USE_MODEL=1 or use prebuilt clue packs."
        )

    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(image_path)

    model, tokenizer, device = _load_model()
    text = _run_minicpm_chat(model, tokenizer, device, str(path), system, user)
    return parse_vision_json(text)


def extract_clues_cached(
    image_path: str,
    *,
    publication: str,
    date: str,
    raw_ocr: str,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Try cache, then model, else raise."""
    base = cache_dir or Path(__file__).resolve().parents[2] / "data" / "clue_cache"
    base.mkdir(parents=True, exist_ok=True)
    key = Path(image_path).stem
    cache_file = base / f"{key}.json"
    if cache_file.is_file():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    payload = extract_clues_from_image(
        image_path,
        publication=publication,
        date=date,
        raw_ocr=raw_ocr,
    )
    cache_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
