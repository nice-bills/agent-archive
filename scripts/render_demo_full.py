#!/usr/bin/env python3
"""Render the full Archive Detective demo video (Walytics-style ~2:26)."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from demo_avatar_overlay import TalkingSegment, floating_avatar_static_talking_filter
DEMO = ROOT / "docs" / "artifacts" / "demo"
SCREENSHOTS = DEMO / "screenshots"
CLIPWISE_OUT = ROOT / ".clipwise" / "output" / "archive_detective_ui.mp4"
COLD_FOLDER = DEMO / "cold_open_folder_seg.mp4"
COLD_STING = DEMO / "cold_open_sting_seg.mp4"
COLD_OPEN = DEMO / "archive_detective_cold_open_27s.mp4"
UI_RAW = DEMO / "ui_walkthrough.mp4"
UI_PIP = DEMO / "ui_walkthrough_pip.mp4"
VOICE_PREVIEW = DEMO / "voice_preview"
ARCHIVIST_TALKING = VOICE_PREVIEW / "archivist_talking.mp4"
ARCHIVIST_PORTRAIT = VOICE_PREVIEW / "archivist_portrait.jpg"
ARCHIVIST_NARRATION = VOICE_PREVIEW / "narration.wav"
COLD_NARRATION = VOICE_PREVIEW / "cold_open_lines.wav"
BOARD_NARRATION = VOICE_PREVIEW / "03_board.wav"
END_CARD = DEMO / "archive_detective_end_card_12s.mp4"
CONCAT_LIST = DEMO / "concat.txt"
MASTER_ASS = DEMO / "full_demo.ass"
OUT = DEMO / "archive_detective_full_demo.mp4"
FOLDER = DEMO / "cold_open_folder.jpg"
ASS_FOLDER = DEMO / "cold_open_folder.ass"
ASS_STING = DEMO / "cold_open_sting.ass"

FPS = 30
W, H = 1920, 1080
FONT_MONO = "JetBrains Mono"
FONT_SERIF = "Noto Serif"

COLD_FOLDER_DUR = 17.0
COLD_STING_DUR = 10.0
COLD_DUR = COLD_FOLDER_DUR + COLD_STING_DUR
END_DUR = 12.0
TARGET_UI_DUR = 107.0  # 27s cold + 107s UI + 12s end ≈ 2:26
# Clipwise holds before "Live generation" step (landing+board+banner+pick ≈ 17s native)
CLIPWISE_GEN_START_NATIVE = 17.0
CLIPWISE_GEN_HOLD_NATIVE = 3.0  # newspaper scan only (~17–20s native); search starts ~20s

# Beat timestamps for frame extraction from final video (seconds)
SCREENSHOT_BEATS = [
    ("01_cold_open_folder", 5.0),
    ("02_until_sting", 18.5),
    ("03_landing", COLD_DUR + 3.0),
    ("04_murder_board", COLD_DUR + 12.0),
    ("05_gallery", COLD_DUR + 20.0),
    ("06_archivist", COLD_DUR + 32.0),
    ("07_cabinet", COLD_DUR + 50.0),
    ("08_lead", COLD_DUR + 60.0),
    ("09_artifact", COLD_DUR + 68.0),
    ("10_search", COLD_DUR + 76.0),
    ("11_deduction", COLD_DUR + 84.0),
    ("12_reveal", COLD_DUR + 92.0),
    ("13_hart_notice", COLD_DUR + 100.0),
    ("14_end_card", COLD_DUR + TARGET_UI_DUR + 4.0),
]


def sec_to_ass(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def run(cmd: list[str], **kwargs) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT, **kwargs)


def probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        text=True,
    )
    return float(out.strip())


def typewriter_events(
    text: str, start: float, cps: float = 24.0, style: str = "Typewriter"
) -> list[str]:
    events: list[str] = []
    end_type = start + len(text) / cps
    for i in range(1, len(text) + 1):
        t0 = start + (i - 1) / cps
        t1 = start + i / cps
        events.append(
            f"Dialogue: 0,{sec_to_ass(t0)},{sec_to_ass(t1)},{style},,0,0,0,,{text[:i]}"
        )
    hold = end_type + 2.0
    events.append(
        f"Dialogue: 0,{sec_to_ass(end_type)},{sec_to_ass(hold)},{style},,0,0,0,,{text}"
    )
    return events


def ass_header() -> str:
    return textwrap.dedent(
        f"""\
        [Script Info]
        ScriptType: v4.00+
        PlayResX: {W}
        PlayResY: {H}

        [V4+ Styles]
        Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
        Style: Typewriter,{FONT_MONO},42,&H00E8DCC8,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,80,80,72,1
        Style: Until,{FONT_SERIF},132,&H00F0E6D8,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,2,0,1,0,2,5,0,0,0,1
        Style: Title,{FONT_SERIF},72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,1,0,1,0,2,5,0,0,0,1
        Style: Close,{FONT_SERIF},76,&H00F5EDE3,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,1,0,1,0,2,5,0,0,0,1
        Style: Stack,{FONT_MONO},30,&H00B8A898,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,0,1,2,80,80,100,1
        Style: Link,{FONT_MONO},26,&H00C8B8A8,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,0,1,2,80,80,130,1

        [Events]
        Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        """
    )


def build_master_ass(ui_start: float, ui_dur: float, total: float) -> str:
    """UI + end-card subtitles only (cold open is pre-burned)."""
    header = textwrap.dedent(
        f"""\
        [Script Info]
        Title: Archive Detective Full Demo
        ScriptType: v4.00+
        PlayResX: {W}
        PlayResY: {H}
        WrapStyle: 0

        [V4+ Styles]
        Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
        Style: Typewriter,{FONT_MONO},40,&H00E8DCC8,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,80,80,68,1
        Style: Close,{FONT_SERIF},72,&H00F5EDE3,&H000000FF,&H00000000,&H80000000,1,0,0,0,100,100,1,0,1,0,2,5,0,0,0,1
        Style: Stack,{FONT_MONO},28,&H00B8A898,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,0,1,2,80,80,110,1
        Style: Link,{FONT_MONO},26,&H00C8B8A8,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,0,1,2,80,80,130,1

        [Events]
        Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        """
    )
    events: list[str] = []
    ui_lines = [
        (0.8, "Real newspaper fragments from Chronicling America."),
        (6.0, "OpenBMB on Modal GPU reads each clipping."),
        (12.0, "MiniCPM-V OCR → MiniCPM5 builds your Evidence Cabinet."),
        (20.0, "Pick a polaroid. One GPU job assembles the mystery."),
        (32.0, "MiniCPM-V on Modal reads the scan — MiniCPM5 drafts the cabinet."),
        (ui_dur * 0.58, "Chase leads. Unlock artifacts. Search the archive."),
        (ui_dur * 0.74, "Submit your deduction. Break the seal."),
        (ui_dur * 0.88, "Hand-built case files load instantly for judges."),
    ]
    for offset, line in ui_lines:
        t = ui_start + offset
        if t >= total - 3:
            continue
        events.extend(typewriter_events(line, t, cps=26.0))

    close_start = total - END_DUR + 1.0
    events.append(
        f"Dialogue: 0,{sec_to_ass(close_start)},{sec_to_ass(total - 1.2)},Close,,0,0,0,,"
        "{\\fad(400,600)}The case is open."
    )
    events.append(
        f"Dialogue: 0,{sec_to_ass(close_start + 2.6)},{sec_to_ass(total - 0.5)},Stack,,0,0,0,,"
        "OpenBMB · MiniCPM-V + MiniCPM5 · Modal · Chronicling America"
    )
    events.append(
        f"Dialogue: 0,{sec_to_ass(close_start + 4.8)},{sec_to_ass(total - 0.3)},Link,,0,0,0,,"
        "huggingface.co/spaces — Archive Detective"
    )
    return header + "\n".join(events) + "\n"


def render_cold_open() -> None:
    line1 = "Library of Congress clippings hide thousands of mysteries."
    line2 = "Nobody was assembling the cases."

    folder_events: list[str] = []
    folder_events.extend(typewriter_events(line1, 1.0))
    folder_events.extend(typewriter_events(line2, 5.6))
    ASS_FOLDER.write_text(ass_header() + "\n".join(folder_events) + "\n", encoding="utf-8")

    folder_vf = (
        f"scale={int(W*1.15)}:{int(H*1.15)}:force_original_aspect_ratio=increase,"
        f"crop={W}:{H},"
        f"zoompan=z='min(zoom+0.00045,1.1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={int(COLD_FOLDER_DUR * FPS)}:s={W}x{H}:fps={FPS},"
        f"format=yuv420p,fade=t=in:st=0:d=0.6,fade=t=out:st={COLD_FOLDER_DUR - 1.2}:d=1.2,"
        f"vignette=angle=PI/4:mode=forward,noise=alls=8:allf=t+u,ass={ASS_FOLDER}"
    )
    run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(FOLDER),
            "-f", "lavfi", "-i",
            f"anoisesrc=d={COLD_FOLDER_DUR}:c=pink:a=0.016,highpass=f=120,lowpass=f=900,"
            f"afade=t=in:st=0:d=1.2,afade=t=out:st={COLD_FOLDER_DUR - 1}:d=1",
            "-filter_complex", f"[0:v]{folder_vf}[vout]",
            "-map", "[vout]", "-map", "1:a", "-t", str(COLD_FOLDER_DUR),
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(COLD_FOLDER),
        ]
    )

    sting_events = [
        "Dialogue: 0,0:00:00.60,0:00:02.20,Until,,0,0,0,,{\\fad(120,180)\\blur2}until",
        "Dialogue: 0,0:00:02.60,0:00:05.80,Title,,0,0,0,,{\\fad(300,500)}Archive Detective",
    ]
    ASS_STING.write_text(ass_header() + "\n".join(sting_events) + "\n", encoding="utf-8")

    sting_vf = (
        f"color=c=0x050608:s={W}x{H}:d={COLD_STING_DUR}:r={FPS},"
        f"vignette=angle=PI/4,noise=alls=6:allf=t+u,ass={ASS_STING}"
    )
    run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", sting_vf,
            "-f", "lavfi", "-i",
            f"anoisesrc=d={COLD_STING_DUR}:c=pink:a=0.012,highpass=f=100,lowpass=f=700,"
            f"afade=t=in:st=0:d=0.4,afade=t=out:st={COLD_STING_DUR - 0.8}:d=0.8",
            "-map", "0:v", "-map", "1:a", "-t", str(COLD_STING_DUR),
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(COLD_STING),
        ]
    )

    cold_list = DEMO / "cold_concat.txt"
    cold_list.write_text(
        f"file '{COLD_FOLDER.resolve()}'\nfile '{COLD_STING.resolve()}'\n",
        encoding="utf-8",
    )
    run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(cold_list),
            "-c", "copy", str(COLD_OPEN),
        ]
    )


def render_end_card() -> None:
    close_ass = DEMO / "end_card.ass"
    close_ass.write_text(
        ass_header()
        + "\n".join(
            [
                "Dialogue: 0,0:00:01.00,0:00:09.50,Close,,0,0,0,,{\\fad(400,600)}The case is open.",
                "Dialogue: 0,0:00:03.20,0:00:10.50,Stack,,0,0,0,,OpenBMB · MiniCPM-V + MiniCPM5 · Modal",
                "Dialogue: 0,0:00:05.00,0:00:11.00,Link,,0,0,0,,Chronicling America · Hugging Face Space",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    vf = (
        f"scale={int(W*1.2)}:{int(H*1.2)}:force_original_aspect_ratio=increase,crop={W}:{H},"
        f"eq=brightness=-0.35:contrast=1.1,"
        f"vignette=angle=PI/3:mode=forward,"
        f"fade=t=in:st=0:d=0.8,fade=t=out:st={END_DUR - 1}:d=1,"
        f"noise=alls=5:allf=t+u,ass={close_ass}"
    )
    audio = (
        f"anoisesrc=d={END_DUR}:c=pink:a=0.014,highpass=f=120,lowpass=f=800,"
        f"afade=t=in:st=0:d=0.8,afade=t=out:st={END_DUR - 1.2}:d=1.2"
    )
    run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(FOLDER),
            "-f", "lavfi", "-i", audio,
            "-filter_complex", f"[0:v]{vf}[vout]",
            "-map", "[vout]", "-map", "1:a", "-t", str(END_DUR),
            "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-c:a", "aac", str(END_CARD),
        ]
    )


def _demo_server_env() -> dict[str, str]:
    env = {**subprocess.os.environ}
    env["ARCHIVE_DETECTIVE_USE_CACHE"] = "1"
    env["ARCHIVE_DETECTIVE_DEMO_PACER"] = "22"
    return env


def ensure_server() -> None:
    import time
    import urllib.request

    def alive() -> bool:
        try:
            urllib.request.urlopen("http://127.0.0.1:7860/", timeout=2)
            return True
        except Exception:
            return False

    if alive():
        subprocess.run(
            ["fuser", "-k", "7860/tcp"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)

    subprocess.Popen(
        ["uv", "run", "python", "main.py"],
        cwd=ROOT,
        env=_demo_server_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(45):
        if alive():
            time.sleep(2)
            return
        time.sleep(1)
    raise RuntimeError("Archive Detective server did not start on :7860")


def ui_generation_window(ui_dur: float, native_dur: float) -> tuple[float, float]:
    """Map Clipwise native generation beat into a time-stretched UI segment."""
    scale = ui_dur / max(native_dur, 1.0)
    start = CLIPWISE_GEN_START_NATIVE * scale
    end = min((CLIPWISE_GEN_START_NATIVE + CLIPWISE_GEN_HOLD_NATIVE) * scale, ui_dur)
    return start, end


def archivist_talking_segments(
    *,
    cold_voice_dur: float,
    archivist_start: float,
    talking_dur: float,
) -> list[TalkingSegment]:
    """Map SadTalker clip to cold-open + delayed board narration in final mix."""
    board_clip_offset = cold_voice_dur
    return [
        (0.0, cold_voice_dur, 0.0),
        (archivist_start, archivist_start + talking_dur, board_clip_offset),
    ]


def probe_archivist_audio_end(
    *,
    cold_voice_dur: float,
    archivist_start: float,
    talking_dur: float,
) -> float:
    """When archivist speech ends in the final mix (board voice is last)."""
    return archivist_start + talking_dur


def overlay_archivist_full(
    src: Path,
    dest: Path,
    *,
    talking_segments: list[TalkingSegment],
) -> bool:
    """Static portrait throughout; SadTalker lips only during archivist audio."""
    if not ARCHIVIST_TALKING.is_file():
        print(f"No talking head at {ARCHIVIST_TALKING}, skipping avatar overlay")
        return False
    if not ARCHIVIST_PORTRAIT.is_file():
        print(f"No portrait at {ARCHIVIST_PORTRAIT}, skipping avatar overlay")
        return False

    dur = probe_duration(src)
    filt = floating_avatar_static_talking_filter(
        portrait_stream="1:v",
        talking_stream="2:v",
        talking_segments=talking_segments,
        placement="corner",
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
            "-loop",
            "1",
            "-i",
            str(ARCHIVIST_PORTRAIT),
            "-stream_loop",
            "-1",
            "-i",
            str(ARCHIVIST_TALKING),
            "-filter_complex",
            filt,
            "-map",
            "[vid]",
            "-map",
            "0:a?",
            "-t",
            f"{dur:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            str(dest),
        ]
    )
    return True


def composite_archivist_pip(
    src: Path,
    dest: Path,
    *,
    native_dur: float | None = None,
) -> tuple[float, float]:
    """Fit UI duration only; avatar overlay happens at final assemble."""
    ui_dur = probe_duration(src)
    native = native_dur or ui_dur
    gen_start, gen_end = ui_generation_window(ui_dur, native)

    if src.resolve() != dest.resolve():
        run(["cp", str(src), str(dest)])
    return gen_start, gen_end


def fit_ui_duration(src: Path, dest: Path, target: float = TARGET_UI_DUR) -> tuple[float, float, float]:
    """Lengthen or shorten UI segment; return (ui_dur, gen_start, gen_end)."""
    native_dur = probe_duration(src)
    dur = native_dur
    if abs(dur - target) < 2.0:
        fitted = src
    else:
        factor = target / dur
        fitted = DEMO / "_ui_fitted.mp4"
        run(
            [
                "ffmpeg", "-y", "-i", str(src),
                "-vf", f"setpts={factor}*PTS",
                "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", str(fitted),
            ]
        )
        dur = probe_duration(fitted)

    gen_start, gen_end = composite_archivist_pip(fitted, dest, native_dur=native_dur)
    return probe_duration(dest), gen_start, gen_end


def record_ui() -> tuple[float, float, float]:
    ensure_server()
    run(["npx", "clipwise@latest", "validate", ".clipwise/scenarios/archive_detective.yaml"])
    run(
        ["npx", "clipwise@latest", "record", ".clipwise/scenarios/archive_detective.yaml"],
        env=_demo_server_env(),
    )
    if not CLIPWISE_OUT.is_file():
        raise FileNotFoundError(f"Clipwise output missing: {CLIPWISE_OUT}")
    return fit_ui_duration(CLIPWISE_OUT, UI_RAW)


def extract_video_frames(video: Path, ui_dur: float) -> None:
    """Pull keyframes from final video into screenshots/."""
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    duration = probe_duration(video)
    beats = list(SCREENSHOT_BEATS)
    if abs(ui_dur - TARGET_UI_DUR) > 15:
        scale = ui_dur / TARGET_UI_DUR
        beats = [
            (name, COLD_DUR + (t - COLD_DUR) * scale if t > COLD_DUR else t)
            for name, t in SCREENSHOT_BEATS
        ]
    for name, t in beats:
        seek = min(max(0.0, t), max(0.0, duration - 0.5))
        out = SCREENSHOTS / f"video_{name}.jpg"
        run(
            [
                "ffmpeg", "-y", "-ss", f"{seek:.3f}", "-i", str(video),
                "-frames:v", "1", "-q:v", "2", str(out),
            ]
        )


def capture_live_screenshots() -> None:
    run(["uv", "run", "python", "scripts/capture_demo_screenshots.py"])


def concat_segments_normalized() -> Path:
    """Concat cold + UI + end with aligned fps/timebase (avoids dropped tail video)."""
    rough = DEMO / "_rough_concat.mp4"
    ui_dur = probe_duration(UI_RAW)
    ui_silence = (
        f"anullsrc=channel_layout=mono:sample_rate=48000,atrim=0:{ui_dur},"
        "asetpts=PTS-STARTPTS"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(COLD_OPEN),
            "-i",
            str(UI_RAW),
            "-i",
            str(END_CARD),
            "-f",
            "lavfi",
            "-i",
            ui_silence,
            "-filter_complex",
            (
                "[0:v]fps=30,format=yuv420p,setpts=PTS-STARTPTS[v0];"
                "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono,"
                "asetpts=PTS-STARTPTS[a0];"
                "[1:v]fps=30,format=yuv420p,setpts=PTS-STARTPTS[v1];"
                "[3:a]asetpts=PTS-STARTPTS[a1];"
                "[2:v]fps=30,format=yuv420p,setpts=PTS-STARTPTS[v2];"
                "[2:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono,"
                "asetpts=PTS-STARTPTS[a2];"
                "[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]"
            ),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(rough),
        ]
    )
    return rough


def ensure_cold_narration() -> Path:
    """Concat per-line cold-open wavs (01 + 02) for t=0 voiceover."""
    if COLD_NARRATION.is_file() and COLD_NARRATION.stat().st_size > 1000:
        return COLD_NARRATION
    parts = [VOICE_PREVIEW / "01_cold.wav", VOICE_PREVIEW / "02_until.wav"]
    missing = [p for p in parts if not p.is_file()]
    if missing:
        return ARCHIVIST_NARRATION
    list_file = VOICE_PREVIEW / "cold_open_concat.txt"
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in parts) + "\n", encoding="utf-8")
    run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", str(COLD_NARRATION),
        ]
    )
    return COLD_NARRATION


def assemble(ui_dur: float, gen_start: float, gen_end: float) -> None:
    total = COLD_DUR + ui_dur + END_DUR
    MASTER_ASS.write_text(build_master_ass(COLD_DUR, ui_dur, total), encoding="utf-8")

    CONCAT_LIST.write_text(
        f"file '{COLD_OPEN.resolve()}'\n"
        f"file '{UI_RAW.resolve()}'\n"
        f"file '{END_CARD.resolve()}'\n",
        encoding="utf-8",
    )

    rough = concat_segments_normalized()
    cold_voice = ensure_cold_narration()
    cold_voice_dur = probe_duration(cold_voice) if cold_voice.is_file() else 0.0
    archivist_start = COLD_DUR + gen_start
    talking_dur = probe_duration(ARCHIVIST_TALKING) if ARCHIVIST_TALKING.is_file() else 0.0
    audio_end = probe_archivist_audio_end(
        cold_voice_dur=cold_voice_dur,
        archivist_start=archivist_start,
        talking_dur=talking_dur,
    )
    talking_segments = archivist_talking_segments(
        cold_voice_dur=cold_voice_dur,
        archivist_start=archivist_start,
        talking_dur=talking_dur,
    )
    avatar_rough = DEMO / "_rough_avatar.mp4"
    if overlay_archivist_full(rough, avatar_rough, talking_segments=talking_segments):
        rough = avatar_rough

    post = (
        f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
        f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,"
        f"vignette=angle=PI/4:mode=forward,"
        f"noise=alls=4:allf=t+u,"
        f"ass={MASTER_ASS}"
    )
    room = (
        f"anoisesrc=d={total}:c=pink:a=0.012,highpass=f=100,lowpass=f=700,"
        f"afade=t=in:st=0:d=2,afade=t=out:st={total - 2}:d=2"
    )
    delay_ms = int(archivist_start * 1000)
    board_voice = ARCHIVIST_TALKING if ARCHIVIST_TALKING.is_file() else BOARD_NARRATION
    has_voice = cold_voice.is_file()
    if has_voice:
        filter_complex = (
            f"[0:v]{post}[v];"
            f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono,"
            f"volume=5.0[seg];"
            f"[1:a]volume=0.3[room];"
            f"[2:a]aresample=48000,volume=1.6[voice0];"
            f"[3:a]aresample=48000,adelay={delay_ms}|{delay_ms},"
            f"volume=1.4[voice1];"
            f"[seg][room][voice0][voice1]amix=inputs=4:duration=first:dropout_transition=0,"
            f"alimiter=limit=0.92[a]"
        )
        cmd = [
            "ffmpeg", "-y", "-i", str(rough),
            "-f", "lavfi", "-i", room,
            "-i", str(cold_voice),
            "-i", str(board_voice),
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            str(OUT),
        ]
    else:
        filter_complex = (
            f"[0:v]{post}[v];"
            f"[0:a]aresample=48000,volume=7.0[seg];"
            f"[1:a]volume=0.22[room];"
            f"[seg][room]amix=inputs=2:duration=first:dropout_transition=0,"
            f"alimiter=limit=0.95[a]"
        )
        cmd = [
            "ffmpeg", "-y", "-i", str(rough),
            "-f", "lavfi", "-i", room,
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            str(OUT),
        ]
    run(cmd)

    (DEMO / "manifest.json").write_text(
        json.dumps(
            {
                "output": str(OUT),
                "duration_s": total,
                "segments": {
                    "cold_open": COLD_DUR,
                    "ui_walkthrough": ui_dur,
                    "end_card": END_DUR,
                },
                "screenshots": str(SCREENSHOTS),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    import sys

    DEMO.mkdir(parents=True, exist_ok=True)
    skip_cold = "--skip-cold-open" in sys.argv
    ui_only = "--ui-only" in sys.argv
    shots_only = "--screenshots-only" in sys.argv
    assemble_only = "--assemble-only" in sys.argv

    if shots_only:
        capture_live_screenshots()
        return

    if not skip_cold and not ui_only and not assemble_only:
        render_cold_open()

    gen_start, gen_end = 0.0, 0.0
    if assemble_only:
        src = CLIPWISE_OUT if CLIPWISE_OUT.is_file() else UI_RAW
        ui_dur, gen_start, gen_end = fit_ui_duration(src, UI_RAW)
    else:
        ui_dur, gen_start, gen_end = record_ui()

    if ui_only:
        print(f"\nUI segment: {UI_RAW} ({ui_dur:.1f}s)")
        return

    render_end_card()
    assemble(ui_dur, gen_start, gen_end)
    extract_video_frames(OUT, ui_dur)
    try:
        capture_live_screenshots()
    except Exception as exc:
        print(f"Live screenshots skipped: {exc}")
    total = probe_duration(OUT)
    print(f"\nDone: {OUT} ({total:.1f}s)")
    print(f"Screenshots: {SCREENSHOTS}/")


if __name__ == "__main__":
    main()
