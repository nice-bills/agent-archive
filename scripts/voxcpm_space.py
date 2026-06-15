#!/usr/bin/env python3
"""Call OpenBMB VoxCPM-Demo HF Space (no local GPU)."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

SPACE = "https://openbmb-voxcpm-demo.hf.space/gradio_api"


def generate_line(text: str, voice_instruction: str, out: Path) -> Path:
    payload = {
        "data": [
            text,
            voice_instruction,
            None,
            False,
            "",
            2.0,
            True,
            False,
        ]
    }
    req = urllib.request.Request(
        f"{SPACE}/call/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        event_id = json.load(resp)["event_id"]

    url = f"{SPACE}/call/generate/{event_id}"
    for _ in range(120):
        with urllib.request.urlopen(url, timeout=120) as resp:
            body = resp.read().decode()
        if body.startswith("event:"):
            for line in body.splitlines():
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    if data:
                        file_info = data[0]
                        file_url = file_info.get("url") or file_info.get("path")
                        if not file_url.startswith("http"):
                            file_url = f"https://openbmb-voxcpm-demo.hf.space/gradio_api/file={file_url}"
                        with urllib.request.urlopen(file_url, timeout=120) as audio_resp:
                            out.write_bytes(audio_resp.read())
                        return out
        time.sleep(2)
    raise TimeoutError("VoxCPM space generation timed out")


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1] if len(sys.argv) > 1 else "test.wav")
    voice = (
        "A late-50s male archivist, warm baritone, measured pace, "
        "dry academic wit, faint library hush"
    )
    generate_line(
        "Library of Congress clippings hide thousands of mysteries.",
        voice,
        out,
    )
    print(out)
