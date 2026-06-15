#!/usr/bin/env python3
"""Push HF_TOKEN + Modal tokens from .env and ~/.modal.toml to the HF Space (quotes stripped)."""

from __future__ import annotations

import argparse
import configparser
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from archive_detective.env import load_project_env

SPACE = "build-small-hackathon/archive-detective-nice-bill"
SPACE_URL = "https://build-small-hackathon-archive-detective-nice-bill.hf.space"
MODAL_TOML = Path.home() / ".modal.toml"
HF_TOKEN_CACHE = Path.home() / ".cache" / "huggingface" / "token"
SECRET_KEYS = ("HF_TOKEN", "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET")


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def load_dotenv_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            out[key] = strip_quotes(value)
    return out


def load_hf_token(*env_files: Path) -> str:
    for key in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
        value = strip_quotes(os.environ.get(key, ""))
        if value:
            return value
    for path in env_files:
        for key in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
            value = load_dotenv_file(path).get(key, "")
            if value:
                return value
    if HF_TOKEN_CACHE.is_file():
        value = strip_quotes(HF_TOKEN_CACHE.read_text(encoding="utf-8"))
        if value:
            return value
    try:
        proc = subprocess.run(
            ["hf", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            value = strip_quotes(proc.stdout.strip())
            if value:
                return value
    except OSError:
        pass
    return ""


def load_modal_tokens(path: Path, *env_files: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for env_path in env_files:
        dot = load_dotenv_file(env_path)
        for key in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"):
            if dot.get(key):
                out[key] = dot[key]
    if out.get("MODAL_TOKEN_ID") and out.get("MODAL_TOKEN_SECRET"):
        return out
    if not path.is_file():
        return out
    cfg = configparser.ConfigParser()
    cfg.read(path)
    profile = cfg.get("default", "profile", fallback="")
    if not profile or profile not in cfg:
        for section in cfg.sections():
            if section != "default" and cfg.has_option(section, "token_id"):
                profile = section
                break
    if not profile or profile not in cfg:
        return out
    sec = cfg[profile]
    if sec.get("token_id"):
        out["MODAL_TOKEN_ID"] = strip_quotes(sec["token_id"])
    if sec.get("token_secret"):
        out["MODAL_TOKEN_SECRET"] = strip_quotes(sec["token_secret"])
    return out


def poll_model_info() -> dict:
    with httpx.Client(timeout=60.0) as client:
        event_id = client.post(
            f"{SPACE_URL}/gradio_api/call/model_info", json={"data": []}
        ).json()["event_id"]
        for _ in range(30):
            time.sleep(1)
            body = client.get(f"{SPACE_URL}/gradio_api/call/model_info/{event_id}").text
            if "event: complete" not in body:
                continue
            for line in body.splitlines():
                if line.startswith("data: "):
                    return json.loads(line[6:])[0]
    return {}


def poll_upload_smoke(hf_token: str) -> dict:
    """Quick upload smoke — pasted OCR, short timeout."""
    sample = ROOT / "assets/uploads/verify_local_upload_smoke_41f63d3e47.jpg"
    if not sample.is_file():
        return {"skipped": "no sample image"}
    import base64

    data_url = "data:image/jpeg;base64," + base64.b64encode(sample.read_bytes()).decode()
    ocr = "mysterious death actress found poisoned after victory ball newspaper clipping"
    with httpx.Client(timeout=30.0) as client:
        event_id = client.post(
            f"{SPACE_URL}/gradio_api/call/generate_from_upload",
            json={"data": [data_url, "restore smoke", ocr, False]},
        ).json()["event_id"]
        for _ in range(45):
            time.sleep(4)
            body = client.get(
                f"{SPACE_URL}/gradio_api/call/generate_from_upload/{event_id}"
            ).text
            if "event: complete" not in body:
                continue
            for line in body.splitlines():
                if line.startswith("data: "):
                    payload = json.loads(line[6:])
                    if payload and isinstance(payload, list):
                        return payload[0] if payload else {}
                    return payload if isinstance(payload, dict) else {}
    return {"error": "upload smoke timed out"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env",
        help="Path to .env (default: repo root .env)",
    )
    parser.add_argument(
        "--smoke-upload",
        action="store_true",
        help="After restart, call generate_from_upload with pasted OCR",
    )
    args = parser.parse_args()

    load_project_env()
    env_files = (args.env_file, ROOT / ".env")
    secrets = {
        "HF_TOKEN": load_hf_token(*env_files),
        **load_modal_tokens(MODAL_TOML, *env_files),
    }
    status = {k: ("set" if secrets.get(k) else "missing") for k in SECRET_KEYS}
    print("LOCAL_STATUS", json.dumps(status))
    if not secrets.get("HF_TOKEN"):
        raise SystemExit(
            "HF_TOKEN missing — set in .env, ~/.cache/huggingface/token, or run hf auth login"
        )

    api = HfApi(token=secrets["HF_TOKEN"])
    print("AUTH_OK", api.whoami().get("name"))
    print("BEFORE", sorted(api.get_space_secrets(SPACE).keys()))

    configured: list[str] = []
    for key in SECRET_KEYS:
        value = secrets.get(key)
        if not value:
            print(f"SKIP {key}")
            continue
        api.add_space_secret(SPACE, key, value, token=secrets["HF_TOKEN"])
        configured.append(key)
        print(f"SET {key}")

    print("AFTER", sorted(api.get_space_secrets(SPACE).keys()))
    if configured:
        api.restart_space(SPACE, token=secrets["HF_TOKEN"])
        print("RESTART ok")
        for i in range(24):
            stage = api.get_space_runtime(SPACE).stage
            print(f"STAGE[{i}] {stage}")
            if stage == "RUNNING":
                break
            time.sleep(10)

    info = poll_model_info()
    print(
        "MODEL_INFO",
        json.dumps(
            {k: info.get(k) for k in ("modal_enabled", "hf_enabled", "stack")},
        ),
    )
    if args.smoke_upload:
        print("UPLOAD_SMOKE", json.dumps(poll_upload_smoke(secrets["HF_TOKEN"])))


if __name__ == "__main__":
    main()
