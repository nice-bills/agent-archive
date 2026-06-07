"""Vision / OCR pipeline — MiniCPM-V-4.6 with heuristic fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from archive_detective.clue_builder import parse_vision_json
from archive_detective.env import load_project_env
from archive_detective.prompts import build_extraction_prompt

load_project_env()

MODEL_ID = os.environ.get("ARCHIVE_DETECTIVE_MODEL", "openbmb/MiniCPM-V-4.6")

_model = None
_processor = None


def model_enabled() -> bool:
    return os.environ.get("ARCHIVE_DETECTIVE_USE_MODEL", "").lower() in {"1", "true", "yes"}


def _hf_token() -> str | None:
    return os.environ.get("HF_TOKEN") or None


def _load_model():
    global _model, _processor
    if _model is not None and _processor is not None:
        return _model, _processor

    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    token = _hf_token()
    _processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True, token=token)
    _model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        trust_remote_code=True,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        attn_implementation="sdpa",
        token=token,
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    _model = _model.eval().to(device)
    return _model, _processor


def _run_minicpm(image_path: str, system: str, user: str) -> str:
    from PIL import Image

    model, processor = _load_model()
    image = Image.open(image_path).convert("RGB")
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": user},
            ],
        },
    ]
    inputs = processor.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)
    out_ids = model.generate(**inputs, max_new_tokens=1024)
    answer = processor.decode(
        out_ids[0][inputs["input_ids"].shape[-1] :],
        skip_special_tokens=True,
    )
    return str(answer)


def extract_clues_from_image(
    image_path: str,
    *,
    publication: str = "Unknown",
    date: str = "unknown",
    raw_ocr: str = "",
) -> dict[str, Any]:
    if not model_enabled():
        raise RuntimeError(
            "Live model disabled. Set ARCHIVE_DETECTIVE_USE_MODEL=1 or use prebuilt clue packs."
        )

    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(image_path)

    system, user = build_extraction_prompt(
        publication=publication,
        date=date,
        raw_ocr=raw_ocr or "(no OCR provided)",
    )
    text = _run_minicpm(str(path), system, user)
    return parse_vision_json(text)


def extract_clues_cached(
    image_path: str,
    *,
    publication: str,
    date: str,
    raw_ocr: str,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
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
