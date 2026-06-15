"""Local / Modal GPU text generation — MiniCPM5-1B (default) for cabinet JSON."""

from __future__ import annotations

import os
import re
from typing import Any

from archive_detective.env import load_project_env
from archive_detective.clue_builder import parse_vision_json

load_project_env()

DEFAULT_TEXT_MODEL = os.environ.get(
    "ARCHIVE_DETECTIVE_TEXT_MODEL",
    "openbmb/MiniCPM5-1B",
)

_model = None
_tokenizer = None
_device: str | None = None


def text_model_id() -> str:
    return os.environ.get("ARCHIVE_DETECTIVE_TEXT_MODEL", DEFAULT_TEXT_MODEL)


def _hf_token() -> str | None:
    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")


def _needs_remote_code(model_id: str) -> bool:
    return "MiniCPM5" not in model_id


def _patch_transformers_compat() -> None:
    """Hub models with trust_remote_code may import removed transformers 5.x symbols."""
    try:
        import transformers.utils.import_utils as import_utils

        if not hasattr(import_utils, "is_torch_fx_available"):
            import_utils.is_torch_fx_available = lambda: True  # type: ignore[attr-defined]
    except ImportError:
        pass


def _strip_thinking(text: str) -> str:
    open_tag, close_tag = "<" + "think" + ">", "</" + "think" + ">"
    if open_tag in text and close_tag in text:
        text = re.sub(
            re.escape(open_tag) + r".*?" + re.escape(close_tag),
            "",
            text,
            flags=re.DOTALL,
        )
    text = re.sub(r"<\|im_start\|>assistant\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def warmup_text_model() -> str:
    """Load MiniCPM text weights for cabinet JSON on Modal or local GPU."""
    global _model, _tokenizer, _device
    if _model is not None and _tokenizer is not None:
        return text_model_id()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    _patch_transformers_compat()
    model_id = text_model_id()
    token = _hf_token()
    remote = _needs_remote_code(model_id)
    _tokenizer = AutoTokenizer.from_pretrained(
        model_id, trust_remote_code=remote, token=token
    )
    _device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if _device == "cuda" else torch.float32
    _model = AutoModelForCausalLM.from_pretrained(
        model_id,
        trust_remote_code=remote,
        torch_dtype=dtype,
        token=token,
    )
    _model = _model.eval().to(_device)
    return model_id


def _build_inputs(tokenizer, messages: list[dict[str, str]], device: str):
    model_id = text_model_id()
    if "MiniCPM5" in model_id:
        inputs = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            enable_thinking=False,
            return_dict=True,
            return_tensors="pt",
        )
        return {k: v.to(device) for k, v in inputs.items()}
    tpl_kwargs: dict[str, Any] = {"add_generation_prompt": True}
    if "MiniCPM4" in model_id:
        tpl_kwargs["enable_thinking"] = False
    prompt_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        **tpl_kwargs,
    )
    return tokenizer([prompt_text], return_tensors="pt").to(device)


def local_chat_json(
    *,
    system: str,
    user: str,
    max_tokens: int = 4096,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """MiniCPM text chat → parsed JSON object."""
    import torch

    model, tokenizer, device = _load()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"{user}\n\n/no_think"},
    ]
    model_inputs = _build_inputs(tokenizer, messages, device)
    input_ids = model_inputs["input_ids"]
    gen_kwargs: dict[str, Any] = {"max_new_tokens": max_tokens, "top_p": 0.95}
    if temperature > 0:
        gen_kwargs.update(do_sample=True, temperature=max(temperature, 0.01))
    else:
        gen_kwargs["do_sample"] = False
    with torch.no_grad():
        out_ids = model.generate(**model_inputs, **gen_kwargs)
    new_tokens = out_ids[0][input_ids.shape[-1] :]
    content = _strip_thinking(tokenizer.decode(new_tokens, skip_special_tokens=True))
    if not content.strip():
        raise RuntimeError("MiniCPM text model returned empty content")
    try:
        return parse_vision_json(content)
    except Exception as exc:
        preview = content[:240].replace("\n", " ")
        raise RuntimeError(f"MiniCPM JSON parse failed ({preview!r}): {exc}") from exc


def _load():
    if _model is None or _tokenizer is None:
        warmup_text_model()
    assert _model is not None and _tokenizer is not None and _device is not None
    return _model, _tokenizer, _device
