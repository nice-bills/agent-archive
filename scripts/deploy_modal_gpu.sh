#!/usr/bin/env bash
# Deploy ONE play GPU function (generate_case_play). Do not run batch unless needed.
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --extra modal
echo "Deploying archive-detective-gpu (generate_case_play only, concurrency_limit=1)…"
uv run modal deploy modal_gpu.py
echo "Done. Play path: ARCHIVE_DETECTIVE_MODAL_PLAY=auto (default when ~/.modal.toml exists)"
