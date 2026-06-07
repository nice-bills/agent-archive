---
title: Archive Detective
emoji: 🕵️
colorFrom: yellow
colorTo: gray
sdk: gradio
sdk_version: "6.16.0"
app_file: app.py
pinned: false
license: mit
short_description: OCR-native micro-mysteries from public-domain news
---

# Archive Detective

Playable micro-mystery machine built from **public-domain newspaper fragments** (Chronicling America / Library of Congress). MiniCPM-V reads noisy clippings; Modal ranks snippets and runs evals — not an archive chatbot.

**Hackathon:** Adventure in Thousand Token Wood · **Model:** [MiniCPM-V 4.6](https://huggingface.co/openbmb/MiniCPM-V-4_6) · **Infra:** [Modal](MODAL.md)

## Quick start (local only — test here first)

```bash
cd archive-detective
uv sync
uv run python scripts/verify_local.py   # smoke test cases + gr.Server build
uv run python main.py                   # custom board → http://127.0.0.1:7860
```

The UI uses **`gradio.Server`** with a custom HTML evidence board (Off-Brand path) — not default Gradio Blocks.

Pick a case, read the clipping, follow leads, hit **Reveal archive facts**.

**Do not deploy** until local verification passes and you've browser-tested the board:

```bash
uv run python scripts/verify_local.py
uv run python scripts/deploy_space.py --confirm-local   # requires HF_TOKEN
```

## Hackathon badge checklist

| Badge | Status | How |
|-------|--------|-----|
| **Off-Brand** | Custom gr.Server UI | `src/archive_detective/static/board/` |
| **Off the Grid** | Prebuilt cases, no cloud at runtime | `data/cases/`, `verify_local.py` |
| **Llama Champion** | llama.cpp OCR extraction | `./scripts/run_llama.sh`, `ARCHIVE_DETECTIVE_USE_LLAMA=1` |
| **Sharing is Caring** | Redacted agent trace | `scripts/prepare_agent_trace.py` |
| **Field Notes** | Build report | `docs/artifacts/field-notes.html` |
| Well-Tuned | Skipped | Prebuilt packs sufficient for demo |

Field notes: `xdg-open docs/artifacts/field-notes.html`

## Local llama.cpp (optional ingest)

```bash
# Download GGUF (example)
hf download Qwen/Qwen2.5-3B-Instruct-GGUF Qwen2.5-3B-Instruct-Q4_K_M.gguf \
  --local-dir ~/.cache/archive-detective/models

./scripts/run_llama.sh   # llama-server on :8080

export ARCHIVE_DETECTIVE_USE_LLAMA=1
uv run python scripts/build_cases_from_ingest.py --top 2
```

## Ingest (real LOC data)

```bash
# Fetch 10–15 snippets → data/raw/snippets/*.json + images
uv run python scripts/fetch_chronicling_america.py --target 15 --rank

# Build playable cases from top-ranked fragments
uv run python scripts/build_cases_from_ingest.py --top 2
```

Data lands in `data/raw/` with citation URL, date, publication, OCR text, and optional IIIF image paths.

## Modal (recommended for batch)

See **[MODAL.md](MODAL.md)** for `modal token`, volume layout, and:

```bash
uv sync --extra modal
modal run modal_app.py::rank_snippets --target 15
modal run modal_app.py::build_clue_packs --top 5
modal run modal_app.py::run_eval
```

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `ARCHIVE_DETECTIVE_USE_MODEL` | off | `1` = run MiniCPM-V locally or on Modal GPU |
| `ARCHIVE_DETECTIVE_MODEL` | `openbmb/MiniCPM-V-4_6` | Hugging Face model id |
| `ARCHIVE_DETECTIVE_USE_LLAMA` | off | `1` = OCR clue extraction via llama-server |
| `ARCHIVE_DETECTIVE_LLAMA_URL` | `http://127.0.0.1:8080` | llama-server base URL |
| `HF_TOKEN` | — | Hub upload only (deploy, agent trace) |

## Project layout

| Path | Role |
|------|------|
| `app.py` | Hugging Face Space entry (src path hack) |
| `main.py` | Local dev entry → custom board |
| `data/cases/` | Playable case JSON (clue-pack graph) |
| `data/raw/` | Ingested Chronicling America snippets |
| `src/archive_detective/` | models, engine, UI, ingest, vision, llama |
| `modal_app.py` | Modal: rank, build packs, eval |
| `scripts/` | fetch, case builder, eval, deploy, verify |

## Demo cases

Hero cases load first: **The Hart Notice** (Georgetown passphrase) and **The Midnight Brief** (1937 organ signal). Read the clipping, inspect evidence cards, follow leads, then **Reveal** for archive facts vs synthetic bridge notes.

## Validate clue packs

```bash
uv run python scripts/preprocess_clue_pack.py data/cases/georgetown_notice.json
```

## Agent trace (Sharing is Caring)

```bash
uv run python scripts/prepare_agent_trace.py              # redact → data/eval/agent_trace_redacted.jsonl
uv run python scripts/prepare_agent_trace.py --upload     # only when HF_TOKEN is set
```

## License

MIT — newspaper content from LOC Chronicling America (public domain).
