#!/usr/bin/env python3
"""Short VoxCPM2 archivist voice preview + PiP composite (~22s)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from demo_avatar_overlay import floating_avatar_filter
OUT = ROOT / "docs" / "artifacts" / "demo" / "voice_preview"
PORTRAIT = OUT / "archivist_portrait.jpg"
VIDEO_OUT = OUT / "archive_detective_voice_preview_22s.mp4"

VOICE_PREFIX = (
    "(A late-50s male archivist, warm baritone, measured pace, dry academic wit, "
    "faint library hush, confident but never salesy) "
)

LINES = [
    ("01_cold", "Library of Congress clippings hide thousands of mysteries."),
    ("02_until", "Nobody was assembling the cases… until now."),
    ("03_board", "Pick a polaroid. One GPU job builds your Evidence Cabinet."),
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=ROOT)


def synthesize_voxcpm_local(line_id: str, text: str, device: str = "cpu") -> Path:
    wav = OUT / f"{line_id}.wav"
    script = f"""
import soundfile as sf
from voxcpm import VoxCPM

model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False, device="{device}", optimize=False)
wav = model.generate(
    text={VOICE_PREFIX!r} + {text!r},
    cfg_value=2.0,
    inference_timesteps=8,
)
sf.write({str(wav)!r}, wav, model.tts_model.sample_rate)
print("wrote", {str(wav)!r})
"""
    run([sys.executable, "-c", script])
    return wav


def synthesize_voxcpm_cli(line_id: str, text: str) -> Path:
    wav = OUT / f"{line_id}.wav"
    full = VOICE_PREFIX + text
    run(
        [
            "voxcpm",
            "design",
            "--text",
            full,
            "--device",
            "cpu",
            "--no-optimize",
            "--output",
            str(wav),
        ]
    )
    return wav


def synthesize_gradio_space(line_id: str, text: str) -> Path:
    wav = OUT / f"{line_id}.wav"
    helper = ROOT / "scripts" / "voxcpm_space_batch.py"
    run([sys.executable, str(helper), str(wav), text])
    return wav


def synthesize_line(line_id: str, text: str) -> Path:
    wav = OUT / f"{line_id}.wav"
    if wav.is_file() and wav.stat().st_size > 1000:
        print(f"  reuse {wav.name}")
        return wav
    if __import__("os").environ.get("VOXCPM_USE_SPACE", "1") == "1":
        try:
            return synthesize_gradio_space(line_id, text)
        except Exception as exc:
            print(f"  HF Space failed ({exc}), trying local…")
    try:
        import voxcpm  # noqa: F401

        return synthesize_voxcpm_local(line_id, text)
    except ImportError:
        pass
    return synthesize_voxcpm_cli(line_id, text)


def concat_audio(wavs: list[Path]) -> Path:
    combined = OUT / "narration.wav"
    list_file = OUT / "audio_concat.txt"
    list_file.write_text("\n".join(f"file '{w.resolve()}'" for w in wavs) + "\n", encoding="utf-8")
    run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", str(combined),
        ]
    )
    return combined


def animate_portrait(audio: Path) -> Path:
    """SadTalker lip-sync (portrait + narration → talking-head clip)."""
    face = OUT / "archivist_talking.mp4"
    if face.is_file() and face.stat().st_size > 50_000:
        print(f"  reuse {face.name}")
        return face
    helper = ROOT / "scripts" / "sadtalker_lipsync.py"
    run(
        [
            sys.executable,
            str(helper),
            str(PORTRAIT),
            str(audio),
            "-o",
            str(face),
        ]
    )
    return face


def build_video(audio: Path) -> None:
    cold = ROOT / "docs/artifacts/demo/archive_detective_cold_open_27s.mp4"
    board = ROOT / "docs/artifacts/demo/screenshots/video_05_gallery.jpg"
    if not PORTRAIT.is_file():
        raise FileNotFoundError(f"Missing portrait: {PORTRAIT}")
    talking = animate_portrait(audio)

    # 22s: 8s cold folder + 8s murder board still + 6s hold
    seg_a = OUT / "_seg_cold.mp4"
    seg_b = OUT / "_seg_board.mp4"
    run(
        [
            "ffmpeg", "-y", "-i", str(cold), "-t", "8", "-an",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(seg_a),
        ]
    )
    run(
        [
            "ffmpeg", "-y", "-loop", "1", "-i", str(board), "-t", "8",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(seg_b),
        ]
    )

    concat = OUT / "visual_concat.mp4"
    clist = OUT / "video_concat.txt"
    clist.write_text(
        f"file '{seg_a.resolve()}'\nfile '{seg_b.resolve()}'\n", encoding="utf-8"
    )
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(clist), "-c", "copy", str(concat)])

    # Centered floating talking head over product footage
    run(
        [
            "ffmpeg", "-y",
            "-i", str(concat),
            "-i", str(audio),
            "-i", str(talking),
            "-filter_complex",
            floating_avatar_filter(face_stream="2:v", placement="center"),
            "-map", "[vid]", "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-shortest",
            str(VIDEO_OUT),
        ]
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not PORTRAIT.is_file():
        fallback = ROOT / "docs/artifacts/demo/cold_open_folder.jpg"
        if fallback.is_file():
            import shutil
            shutil.copy(fallback, PORTRAIT)

    print("Synthesizing archivist lines with VoxCPM2…")
    wavs = [synthesize_line(lid, text) for lid, text in LINES]
    audio = concat_audio(wavs)
    print("Compositing preview video…")
    build_video(audio)
    print(f"\nPreview: {VIDEO_OUT}")


if __name__ == "__main__":
    main()
