"""Hugging Face Space entrypoint for Archive Detective."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from archive_detective.ui import build_app  # noqa: E402

demo = build_app()

if __name__ == "__main__":
    demo.launch()
