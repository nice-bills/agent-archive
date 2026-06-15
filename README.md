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
short_description: Micro-mysteries from public-domain news clippings
tags:
  - thousand-token-wood
  - off-brand
  - field-notes
  - sharing-is-caring
---

# Archive Detective

Play short mystery cases built from **public-domain newspaper fragments** (Chronicling America / Library of Congress).

Pick a curated case **or** generate a new Evidence Cabinet from bundled LOC clippings.

**Live Space:** [build-small-hackathon/archive-detective-nice-bill](https://huggingface.co/spaces/build-small-hackathon/archive-detective-nice-bill)

**Gallery polaroids:** pre-built cabinets in `data/generated_cases/` open instantly (no Modal wait). Use **Regenerate** for a fresh OpenBMB GPU run.

**Live path (OpenBMB):** one Modal GPU job per regenerate — MiniCPM-V-4.6 OCR → MiniCPM5-1B cabinet JSON.

**Demo video:** _(add YouTube/Loom URL before judging)_

**Social post:** _(add X/LinkedIn link before judging)_

**Hackathon:** Adventure in Thousand Token Wood · **Models:** [MiniCPM-V-4.6](https://huggingface.co/openbmb/MiniCPM-V-4.6) (OCR) + [MiniCPM5-1B](https://huggingface.co/openbmb/MiniCPM5-1B) (cabinet JSON) · **Infra:** [Modal](MODAL.md) (`generate_case_play`, one A10G job per pick)

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
| **Off-Brand** | ✅ Custom `gr.Server` board | `src/archive_detective/static/board/` |
| **OpenBMB special** | ✅ Live play path | Modal `generate_case_play` — MiniCPM-V OCR → MiniCPM5 cabinet |
| **Sharing is Caring** | ✅ Uploaded | [nice-bill/archive-detective-agent-trace](https://huggingface.co/datasets/nice-bill/archive-detective-agent-trace) |
| **Field Notes** | ✅ Ready | [docs/artifacts/field-notes.html](docs/artifacts/field-notes.html) (or HF blog draft) |
| **Llama Champion** | Optional ingest | `./scripts/run_llama.sh`, `ARCHIVE_DETECTIVE_USE_LLAMA=1` |
| Off the Grid | Partial | Curated cases offline; gallery/upload need Modal or HF |

**Field notes:** [docs/artifacts/field-notes.html](docs/artifacts/field-notes.html) — `xdg-open docs/artifacts/field-notes.html` (publish as HF blog post for judges if preferred)

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
| `ARCHIVE_DETECTIVE_MODAL_PLAY` | `auto` | One Modal GPU job per gallery/upload (`1` / `0`) |
| `ARCHIVE_DETECTIVE_MODEL` | `openbmb/MiniCPM-V-4.6` | Vision / OCR model |
| `ARCHIVE_DETECTIVE_TEXT_MODEL` | `openbmb/MiniCPM5-1B` | Cabinet JSON model on Modal |
| `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` | — | Call deployed `generate_case_play` |
| `HF_TOKEN` | — | Weights on Modal + Space deploy + HF fallback |
| `ARCHIVE_DETECTIVE_USE_MODEL` | off | `1` = local MiniCPM-V (dev) |
| `ARCHIVE_DETECTIVE_USE_LLAMA` | off | `1` = llama.cpp ingest path |
| `ARCHIVE_DETECTIVE_USE_CACHE` | off | Dev only — do not use for demo |

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
