#!/usr/bin/env python3
"""Generate one VoxCPM line via HF Space. Usage: voxcpm_space_batch.py OUT.wav 'text'"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from voxcpm_space import generate_line  # noqa: E402

VOICE = (
    "A late-50s male archivist, warm baritone, measured pace, "
    "dry academic wit, faint library hush"
)

if __name__ == "__main__":
    out = Path(sys.argv[1])
    text = sys.argv[2]
    generate_line(text, VOICE, out)
    print(out)
