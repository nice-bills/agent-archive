#!/usr/bin/env python3
"""Push HF_TOKEN + Modal tokens from .env and ~/.modal.toml to the HF Space (quotes stripped)."""

from __future__ import annotations

import configparser
import json
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
SECRET_KEYS = ("HF_TOKEN", "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET")


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def load_modal_tokens(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    cfg = configparser.ConfigParser()
    cfg.read(path)
    profile = cfg.get("default", "profile", fallback="")
    if not profile or profile not in cfg:
        for section in cfg.sections():
            if section != "default" and cfg.has_option(section, "token_id"):
                profile = section
                break
    if not profile or profile not in cfg:
        return {}
    sec = cfg[profile]
    out: dict[str, str] = {}
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


def main() -> None:
    load_project_env()
    import os

    secrets = {
        "HF_TOKEN": strip_quotes(os.environ.get("HF_TOKEN", "")),
        **load_modal_tokens(MODAL_TOML),
    }
    status = {k: ("set" if secrets.get(k) else "missing") for k in SECRET_KEYS}
    print("LOCAL_STATUS", json.dumps(status))
    if not secrets.get("HF_TOKEN"):
        raise SystemExit("HF_TOKEN missing — set in .env or run hf auth login")

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


if __name__ == "__main__":
    main()
