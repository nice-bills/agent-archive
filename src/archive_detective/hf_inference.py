"""Hosted Hugging Face inference — no local model weights."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from archive_detective.env import load_project_env

load_project_env()

DEFAULT_MODEL = os.environ.get(
    "ARCHIVE_DETECTIVE_HF_MODEL",
    "Qwen/Qwen2.5-7B-Instruct",
)
DEFAULT_VISION_MODEL = os.environ.get(
    "ARCHIVE_DETECTIVE_HF_VISION_MODEL",
    "openbmb/MiniCPM-V-4_6",
)


def hf_token() -> str | None:
    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")


def hf_enabled() -> bool:
    return bool(hf_token())


def parse_json_blob(text: str) -> dict[str, Any]:
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Model response contained no JSON object")
    return json.loads(raw[start : end + 1])


def _client():
    from huggingface_hub import InferenceClient

    token = hf_token()
    if not token:
        raise RuntimeError("HF_TOKEN is not set — cannot call hosted inference")
    return InferenceClient(token=token)


def chat_completion_json(
    *,
    system: str,
    user: str,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Text-only hosted chat → parsed JSON object."""
    client = _client()
    model_id = model or DEFAULT_MODEL
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception as exc:
        raise RuntimeError(f"HF inference failed for {model_id}: {exc}") from exc

    choices = getattr(response, "choices", None) or []
    if not choices:
        raise RuntimeError("HF inference returned no choices")
    message = choices[0].message
    content = getattr(message, "content", None) or ""
    if not content:
        raise RuntimeError("HF inference returned empty content")
    return parse_json_blob(str(content))


def chat_completion_json_with_image(
    *,
    system: str,
    user: str,
    image_url: str,
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Vision + text hosted chat → parsed JSON (falls back to text-only)."""
    client = _client()
    model_id = model or DEFAULT_VISION_MODEL
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": user},
            ],
        },
    ]
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choices = getattr(response, "choices", None) or []
        if choices:
            content = getattr(choices[0].message, "content", "") or ""
            if content:
                return parse_json_blob(str(content))
    except Exception:
        pass
    return chat_completion_json(
        system=system,
        user=user,
        model=DEFAULT_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def hf_health(model: str | None = None) -> bool:
    if not hf_enabled():
        return False
    try:
        client = _client()
        model_id = model or DEFAULT_MODEL
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "Reply with OK"}],
            max_tokens=8,
            temperature=0.0,
        )
        return bool(getattr(response, "choices", None))
    except Exception:
        return False
