#!/usr/bin/env python3
"""Animate a portrait with SadTalker (image + audio → talking-head video)."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SADTALKER = Path(os.environ.get("SADTALKER_ROOT", "/tmp/SadTalker"))
CHECKPOINT_REPO = os.environ.get("SADTALKER_CHECKPOINT_REPO", "guruuewe/sadtalker_checkpoints")
AUX_REPO = os.environ.get("SADTALKER_AUX_REPO", "vinthony/SadTalker")

# (repo_id, remote path, local path under SadTalker root)
HF_FILES: list[tuple[str, str, str]] = [
    (CHECKPOINT_REPO, "mapping_00229-model.pth.tar", "checkpoints/mapping_00229-model.pth.tar"),
    (CHECKPOINT_REPO, "SadTalker_V0.0.2_256.safetensors", "checkpoints/SadTalker_V0.0.2_256.safetensors"),
    (AUX_REPO, "BFM_Fitting/similarity_Lm3D_all.mat", "src/config/similarity_Lm3D_all.mat"),
    (AUX_REPO, "hub/checkpoints/2DFAN4-cd938726ad.zip", "checkpoints/hub/checkpoints/2DFAN4-cd938726ad.zip"),
    (AUX_REPO, "hub/checkpoints/s3fd-619a316812.pth", "checkpoints/hub/checkpoints/s3fd-619a316812.pth"),
]


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=cwd or ROOT)


def ensure_sadtalker_repo(repo: Path) -> None:
    if (repo / "inference.py").is_file():
        return
    repo.parent.mkdir(parents=True, exist_ok=True)
    run(["git", "clone", "--depth", "1", "https://github.com/OpenTalker/SadTalker.git", str(repo)])


def ensure_checkpoints(repo: Path) -> None:
    missing = [dest for _, _, dest in HF_FILES if not (repo / dest).is_file()]
    if not missing:
        return
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError("huggingface_hub required: uv pip install huggingface_hub") from exc

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_HUB_TOKEN")
    print(f"Downloading {len(missing)} SadTalker checkpoint file(s)…")
    for hub_repo, filename, dest in HF_FILES:
        target = repo / dest
        if target.is_file():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"  {hub_repo}/{filename}")
        path = hf_hub_download(
            repo_id=hub_repo,
            filename=filename,
            token=token,
            local_dir=str(repo),
        )
        downloaded = Path(path)
        if downloaded.resolve() != target.resolve():
            shutil.copy2(downloaded, target)


_NUMPY_ALIAS_RE = re.compile(
    r"np\.(float|int|bool|object|str|complex)(?![0-9a-zA-Z_])"
)


def _fix_numpy_aliases(text: str) -> str:
    replacements = {
        "float": "float64",
        "int": "int64",
        "bool": "bool_",
        "object": "object_",
        "str": "str_",
        "complex": "complex128",
    }

    def repl(match: re.Match[str]) -> str:
        return f"np.{replacements[match.group(1)]}"

    return _NUMPY_ALIAS_RE.sub(repl, text)


def _patch_file_aliases(path: Path) -> None:
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    fixed = text.replace("np.VisibleDeprecationWarning", "DeprecationWarning")
    fixed = _fix_numpy_aliases(fixed)
    if fixed != text:
        path.write_text(fixed, encoding="utf-8")


def _patch_numpy2_preprocess(repo: Path) -> None:
  """lstsq + scalar coercion fixes for numpy 2.x."""
  face3d = repo / "src/face3d/util/preprocess.py"
  if face3d.is_file():
    text = face3d.read_text(encoding="utf-8")
    if "k = np.asarray(k).reshape(-1)" not in text:
      text = text.replace(
        "    k, _, _, _ = np.linalg.lstsq(A, b)\n\n    R1 = k[0:3]",
        "    k, _, _, _ = np.linalg.lstsq(A, b)\n    k = np.asarray(k).reshape(-1)\n\n    R1 = k[0:3]",
      )
    if "s = float(s)" not in text:
      text = text.replace(
        "def resize_n_crop_img(img, lm, t, s, target_size=224., mask=None):\n    w0, h0 = img.size\n    w = (w0*s).astype(np.int32)",
        "def resize_n_crop_img(img, lm, t, s, target_size=224., mask=None):\n    w0, h0 = img.size\n    s = float(s)\n    t = np.asarray(t).reshape(-1)\n    w = int(w0 * s)",
      )
      text = text.replace(
        "    h = (h0*s).astype(np.int32)\n    left = (w/2 - target_size/2 + float((t[0] - w0/2)*s)).astype(np.int32)\n    right = left + target_size\n    up = (h/2 - target_size/2 + float((h0/2 - t[1])*s)).astype(np.int32)\n    below = up + target_size",
        "    h = int(h0 * s)\n    left = int(w / 2 - target_size / 2 + (float(t[0]) - w0 / 2) * s)\n    right = left + int(target_size)\n    up = int(h / 2 - target_size / 2 + (h0 / 2 - float(t[1])) * s)\n    below = up + int(target_size)",
      )
    text = text.replace(
      "    trans_params = np.array([w0, h0, s, t[0], t[1]])",
      "    trans_params = np.array([w0, h0, float(s), float(t[0]), float(t[1])], dtype=np.float32)",
    )
    face3d.write_text(text, encoding="utf-8")

  utils_pp = repo / "src/utils/preprocess.py"
  if utils_pp.is_file():
    text = utils_pp.read_text(encoding="utf-8")
    fixed = text.replace(
      "trans_params = np.array([float(item) for item in np.hsplit(trans_params, 5)]).astype(np.float32)",
      "trans_params = np.asarray(trans_params, dtype=np.float32).reshape(-1)",
    )
    if fixed != text:
      utils_pp.write_text(fixed, encoding="utf-8")


def patch_sadtalker_compat(repo: Path) -> None:
    """SadTalker predates numpy 2.x and always imports gfpgan even when unused."""
    for rel in (
        "src/face3d/util/preprocess.py",
        "src/face3d/util/my_awing_arch.py",
        "src/face3d/models/arcface_torch/torch2onnx.py",
        "src/face3d/models/arcface_torch/utils/plot.py",
        "src/face3d/models/arcface_torch/onnx_ijbc.py",
        "src/face3d/models/arcface_torch/eval_ijbc.py",
    ):
        _patch_file_aliases(repo / rel)

    _patch_numpy2_preprocess(repo)

    enhancer = repo / "src/utils/face_enhancer.py"
    if enhancer.is_file():
        text = enhancer.read_text(encoding="utf-8")
        if "from gfpgan import GFPGANer" in text and "GFPGANer = None" not in text:
            text = text.replace(
                "from gfpgan import GFPGANer",
                "GFPGANer = None\ntry:\n    from gfpgan import GFPGANer\nexcept ImportError:\n    pass",
            )
            enhancer.write_text(text, encoding="utf-8")


def lipsync(
    portrait: Path,
    audio: Path,
    out: Path,
    *,
    sadtalker_root: Path = DEFAULT_SADTALKER,
    size: int = 256,
    still: bool = True,
    cpu: bool = True,
) -> Path:
    if not portrait.is_file():
        raise FileNotFoundError(portrait)
    if not audio.is_file():
        raise FileNotFoundError(audio)

    out = out.resolve()
    portrait = portrait.resolve()
    audio = audio.resolve()

    ensure_sadtalker_repo(sadtalker_root)
    ensure_checkpoints(sadtalker_root)
    patch_sadtalker_compat(sadtalker_root)

    work = out.parent / f".sadtalker_{out.stem}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        str(sadtalker_root / "inference.py"),
        "--source_image",
        str(portrait.resolve()),
        "--driven_audio",
        str(audio.resolve()),
        "--checkpoint_dir",
        str(sadtalker_root / "checkpoints"),
        "--result_dir",
        str(work),
        "--size",
        str(size),
        "--preprocess",
        "crop",
    ]
    if still:
        cmd.append("--still")
    if cpu:
        cmd.append("--cpu")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(sadtalker_root) + os.pathsep + env.get("PYTHONPATH", "")
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=sadtalker_root, env=env)

    candidates = sorted(work.rglob("*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise RuntimeError(f"SadTalker produced no mp4 under {work}")

    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidates[0], out)
    print(f"Talking head: {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("portrait", type=Path)
    parser.add_argument("audio", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--sadtalker-root", type=Path, default=DEFAULT_SADTALKER)
    parser.add_argument("--size", type=int, default=256, choices=(256, 512))
    parser.add_argument("--gpu", action="store_true", help="Use CUDA if available")
    args = parser.parse_args()

    lipsync(
        args.portrait,
        args.audio,
        args.output,
        sadtalker_root=args.sadtalker_root,
        size=args.size,
        cpu=not args.gpu,
    )


if __name__ == "__main__":
    main()
