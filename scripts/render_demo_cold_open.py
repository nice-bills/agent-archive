#!/usr/bin/env python3
"""Render a 15s noir cold-open for the Archive Detective demo video."""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "docs" / "artifacts" / "demo"
OUT = DEMO / "archive_detective_cold_open_15s.mp4"
FOLDER = DEMO / "cold_open_folder.jpg"
LANDING = DEMO / "landing_screenshot.png"
ASS = DEMO / "cold_open.ass"
FONT_MONO = "JetBrains Mono"
FONT_SERIF = "Noto Serif"

FPS = 30
W, H = 1920, 1080
DURATION = 15.0


def sec_to_ass(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def typewriter_events(
    text: str,
    start: float,
    cps: float = 22.0,
    style: str = "Typewriter",
) -> list[str]:
    events: list[str] = []
    for i in range(1, len(text) + 1):
        chunk = text[:i]
        t0 = start + (i - 1) / cps
        t1 = start + i / cps
        events.append(
            f"Dialogue: 0,{sec_to_ass(t0)},{sec_to_ass(t1)},{style},,0,0,0,,{chunk}"
        )
    hold_end = start + len(text) / cps + 2.5
    events.append(
        f"Dialogue: 0,{sec_to_ass(start + len(text) / cps)},"
        f"{sec_to_ass(hold_end)},{style},,0,0,0,,{text}"
    )
    return events


def build_ass() -> str:
    line1 = "Library of Congress clippings hide thousands of mysteries."
    line2 = "Nobody was assembling the cases."

    header = textwrap.dedent(
        f"""\
        [Script Info]
        Title: Archive Detective Cold Open
        ScriptType: v4.00+
        PlayResX: {W}
        PlayResY: {H}
        WrapStyle: 0

        [V4+ Styles]
        Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
        Style: Typewriter,{FONT_MONO},42,&H00E8DCC8,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,80,80,72,1
        Style: Until,{FONT_SERIF},120,&H00F0E6D8,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,0,2,5,0,0,0,1
        Style: Title,{FONT_SERIF},68,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,1,0,1,0,2,5,0,0,0,1

        [Events]
        Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        """
    )

    events: list[str] = []
    events.extend(typewriter_events(line1, start=1.0, cps=24.0))
    events.extend(typewriter_events(line2, start=5.8, cps=24.0))
    events.append(
        "Dialogue: 0,0:00:11.20,0:00:12.40,Until,,0,0,0,,{\\fad(200,200)}until"
    )
    events.append(
        "Dialogue: 0,0:00:12.60,0:00:14.80,Title,,0,0,0,,"
        "{\\fad(300,400)}Archive Detective"
    )
    return header + "\n".join(events) + "\n"


def run_ffmpeg() -> None:
    folder_vf = (
        f"scale={W*1.15}:{H*1.15}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"zoompan=z='min(zoom+0.00045,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={int(DURATION * FPS)}:s={W}x{H}:fps={FPS},"
        f"format=yuv420p"
    )

    post = (
        "fade=t=in:st=0:d=0.6,"
        "fade=t=out:st=10.4:d=0.9,"
        "vignette=angle=PI/4:mode=forward,"
        "noise=alls=8:allf=t+u,"
        f"ass={ASS}"
    )

    filter_complex = f"[0:v]{folder_vf},{post}[vout]"

    # Low noir room tone under the cold open
    audio_filter = (
        "anoisesrc=d=15:c=pink:a=0.018,"
        "highpass=f=120,lowpass=f=900,"
        "afade=t=in:st=0:d=1.5,"
        "afade=t=out:st=13.2:d=1.8"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(FOLDER),
        "-f",
        "lavfi",
        "-i",
        audio_filter,
        "-filter_complex",
        filter_complex,
        "-map",
        "[vout]",
        "-map",
        "1:a",
        "-t",
        str(DURATION),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(OUT),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    DEMO.mkdir(parents=True, exist_ok=True)
    ASS.write_text(build_ass(), encoding="utf-8")
    run_ffmpeg()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
