#!/usr/bin/env bash
# Archive Detective — Modal runner (run from repo root after `modal token new`)
set -euo pipefail
cd "$(dirname "$0")/.."

ACTION="${1:-all}"
TARGET="${TARGET:-3}"
TOP="${TOP:-1}"

run() {
  echo ">> $*"
  uv run modal run "$@"
}

check_auth() {
  if ! uv run modal secret list &>/dev/null; then
    echo "Modal is not authenticated."
    echo "Run once:  uv run modal token new"
    echo "Then retry:  ./scripts/run_modal.sh $ACTION"
    exit 1
  fi
}

check_auth

case "$ACTION" in
  rank)
    run modal_app.py::rank_snippets --target "$TARGET"
    ;;
  eval)
    run modal_app.py::run_eval
    ;;
  packs)
    if [[ -z "${HF_TOKEN:-}" ]]; then
      echo "Tip: export HF_TOKEN=hf_... for build_clue_packs (or: modal secret create huggingface HF_TOKEN=...)"
    fi
    run modal_gpu.py::build_clue_packs --top "$TOP"
    ;;
  pull)
    mkdir -p data/raw data/eval data/clue_packs
    uv run modal volume get archive-detective-data raw/ranked.json data/raw/ranked.json || true
    uv run modal volume get archive-detective-data eval/eval.json data/eval/eval.json || true
    uv run modal volume get archive-detective-data eval/summary.md data/eval/summary.md || true
    echo "Pulled ranked.json + eval artifacts into data/"
    ;;
  all)
    run modal_app.py::rank_snippets --target "$TARGET"
    run modal_app.py::run_eval
    echo "Skipping build_clue_packs in 'all' (GPU cost). Run: ./scripts/run_modal.sh packs"
  ;;
  *)
    echo "Usage: $0 {rank|eval|packs|pull|all}"
    echo "  TARGET=15 TOP=5 $0 rank"
    exit 1
    ;;
esac
