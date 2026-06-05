#!/usr/bin/env python3
"""Generate a sepia placeholder clipping image for demo cases."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "georgetown_notice.png"

TEXT = (
    "GEORGETOWN — M. Hart will receive inquiries at the room\n"
    "above the stationers, 14th St., after 8 p.m.\n"
    "Bring the phrase. No names at the desk."
)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    width, height = 720, 420
    img = Image.new("RGB", (width, height), "#e8dcc8")
    draw = ImageDraw.Draw(img)
    draw.rectangle((24, 24, width - 24, height - 24), outline="#8a7355", width=2)
    try:
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSerif.ttf", 22)
        small = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSerif.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
        small = font
    draw.text((48, 48), "EVENING STAR — Mar 14, 1912", fill="#5c4a38", font=small)
    draw.multiline_text((48, 90), TEXT, fill="#2a2118", font=font, spacing=8)
    draw.text((48, height - 56), "Chronicling America · demo artifact", fill="#7a6a58", font=small)
    img = img.convert("L").convert("RGB")
    img.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
