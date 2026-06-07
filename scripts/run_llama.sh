#!/usr/bin/env bash
# Start llama-server for Archive Detective OCR → clue extraction (Off the Grid).
#
# Download a GGUF model first, e.g.:
#   hf download Qwen/Qwen2.5-3B-Instruct-GGUF \
#     Qwen2.5-3B-Instruct-Q4_K_M.gguf --local-dir ~/.cache/archive-detective/models
#
# Then set ARCHIVE_DETECTIVE_LLAMA_MODEL to the GGUF path and run this script.

set -euo pipefail

LLAMA_BIN="${ARCHIVE_DETECTIVE_LLAMA_BIN:-$HOME/.local/bin/llama-server}"
MODEL="${ARCHIVE_DETECTIVE_LLAMA_MODEL:-$HOME/.cache/archive-detective/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf}"
HOST="${ARCHIVE_DETECTIVE_LLAMA_HOST:-127.0.0.1}"
PORT="${ARCHIVE_DETECTIVE_LLAMA_PORT:-8080}"
CTX="${ARCHIVE_DETECTIVE_LLAMA_CTX:-4096}"

if [[ ! -x "$LLAMA_BIN" ]]; then
  echo "llama-server not found at $LLAMA_BIN" >&2
  echo "Build or install llama.cpp and set ARCHIVE_DETECTIVE_LLAMA_BIN." >&2
  exit 1
fi

if [[ ! -f "$MODEL" ]]; then
  echo "GGUF model not found: $MODEL" >&2
  echo "Download one (see script header) or set ARCHIVE_DETECTIVE_LLAMA_MODEL." >&2
  exit 1
fi

echo "Archive Detective llama-server"
echo "  model: $MODEL"
echo "  url:   http://${HOST}:${PORT}"
echo ""
echo "In another terminal:"
echo "  export ARCHIVE_DETECTIVE_USE_LLAMA=1"
echo "  export ARCHIVE_DETECTIVE_LLAMA_URL=http://${HOST}:${PORT}"
echo "  uv run python scripts/build_cases_from_ingest.py --top 2"
echo ""

exec "$LLAMA_BIN" \
  --model "$MODEL" \
  --host "$HOST" \
  --port "$PORT" \
  --ctx-size "$CTX" \
  --parallel 2 \
  --cont-batching
