#!/usr/bin/env python3
"""Redact and export Cursor agent transcript for HF dataset (Sharing is Caring badge)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from archive_detective.env import load_project_env

load_project_env()

DEFAULT_TRANSCRIPT = Path(
    "/home/bills/.cursor/projects/home-bills-code-archive-detective/agent-transcripts/"
    "08eda1f2-a074-42af-8520-a2baf67c66df/08eda1f2-a074-42af-8520-a2baf67c66df.jsonl"
)
DEFAULT_OUT = ROOT / "data" / "eval" / "agent_trace_redacted.jsonl"

# Patterns to scrub before any Hub upload.
SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"hf_[A-Za-z0-9]{20,}"), "hf_[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "sk-[REDACTED]"),
    (re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"]?\S+['\"]?", re.I), r"\1=[REDACTED]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._-]+"), "Bearer [REDACTED]"),
]


def redact_text(text: str) -> str:
    out = text
    for pat, repl in SECRET_PATTERNS:
        out = pat.sub(repl, out)
    return out


def redact_obj(obj: object) -> object:
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, list):
        return [redact_obj(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    return obj


def prepare_trace(src: Path, dest: Path) -> int:
    if not src.is_file():
        raise SystemExit(f"Transcript not found: {src}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with src.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSONL line {line_no}: {exc}") from exc
            rows.append(redact_obj(row))

    with dest.open("w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Redacted {len(rows)} turns → {dest}")
    return len(rows)


def maybe_upload(dest: Path, repo: str) -> None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF_TOKEN not set — skipping upload (local redacted file only).")
        return

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    api.create_repo(repo, repo_type="dataset", exist_ok=True, private=False)
    api.upload_file(
        path_or_fileobj=str(dest),
        path_in_repo="agent_trace_redacted.jsonl",
        repo_id=repo,
        repo_type="dataset",
        commit_message="Add redacted Archive Detective agent trace",
    )
    api.update_repo_settings(repo, private=False, repo_type="dataset")
    print(f"Uploaded (public): https://huggingface.co/datasets/{repo}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Redact agent trace for HF dataset")
    parser.add_argument("--input", type=Path, default=DEFAULT_TRANSCRIPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload to HF dataset (requires HF_TOKEN in .env)",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Target dataset repo (default: <user>/archive-detective-agent-trace)",
    )
    args = parser.parse_args()

    count = prepare_trace(args.input, args.output)
    if args.upload:
        if count == 0:
            raise SystemExit("Nothing to upload.")
        from huggingface_hub import HfApi

        token = os.environ.get("HF_TOKEN")
        if not token:
            raise SystemExit("Refusing --upload without HF_TOKEN in .env")
        user = HfApi(token=token).whoami()["name"]
        repo = args.repo or f"{user}/archive-detective-agent-trace"
        maybe_upload(args.output, repo)
    else:
        print("Run with --upload to push (only when HF_TOKEN is set).")


if __name__ == "__main__":
    main()
