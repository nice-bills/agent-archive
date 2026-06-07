"""Local OCR → clue extraction via llama.cpp llama-server (Off the Grid badge)."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from archive_detective.clue_builder import parse_vision_json
from archive_detective.env import load_project_env
from archive_detective.prompts import build_extraction_prompt

load_project_env()

DEFAULT_BASE = os.environ.get("ARCHIVE_DETECTIVE_LLAMA_URL", "http://127.0.0.1:8080")
DEFAULT_MODEL = os.environ.get("ARCHIVE_DETECTIVE_LLAMA_MODEL", "local")


def llama_enabled() -> bool:
    return os.environ.get("ARCHIVE_DETECTIVE_USE_LLAMA", "").lower() in {"1", "true", "yes"}


def llama_health(base_url: str | None = None, *, timeout: float = 2.0) -> bool:
    url = (base_url or DEFAULT_BASE).rstrip("/")
    try:
        r = httpx.get(f"{url}/health", timeout=timeout)
        return r.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


def extract_clues_from_ocr(
    *,
    publication: str,
    date: str,
    raw_ocr: str,
    base_url: str | None = None,
    model: str | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Call llama-server /v1/chat/completions on OCR text; return parsed clue JSON."""
    if not raw_ocr.strip():
        raise ValueError("raw_ocr is empty")

    base = (base_url or DEFAULT_BASE).rstrip("/")
    model_id = model or DEFAULT_MODEL
    system, user = build_extraction_prompt(publication=publication, date=date, raw_ocr=raw_ocr)

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
        "response_format": {"type": "json_object"},
    }

    with httpx.Client(timeout=timeout) as client:
        r = client.post(f"{base}/v1/chat/completions", json=payload)
        r.raise_for_status()
        data = r.json()

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("llama-server returned no choices")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("llama-server returned empty content")

    try:
        return parse_vision_json(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"llama-server did not return valid JSON: {exc}") from exc
