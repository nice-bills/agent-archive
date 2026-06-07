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
short_description: OCR-native micro-mysteries from public-domain newspaper fragments
---

# Archive Detective

Playable micro-mystery machine built from **public-domain newspaper fragments** (Chronicling America / Library of Congress). MiniCPM-V reads noisy clippings; Modal ranks snippets and runs evals — not an archive chatbot.

**Hackathon:** Adventure in Thousand Token Wood · **Model:** [MiniCPM-V 4.6](https://huggingface.co/openbmb/MiniCPM-V-4_6) · **Infra:** [Modal](MODAL.md)

## Quick start

```bash
cd archive-detective
cp .env.example .env   # add HF_TOKEN for MiniCPM / Hub
uv sync
uv run python main.py   # http://127.0.0.1:7860
```

**Secrets:** `.env` is gitignored. For Modal GPU jobs, create `modal secret create huggingface HF_TOKEN=hf_...` (see [MODAL.md](MODAL.md)).

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

## Project layout

| Path | Role |
|------|------|
| `app.py` | Hugging Face Space entry (src path hack) |
| `data/cases/` | Playable case JSON (clue-pack graph) |
| `data/raw/` | Ingested Chronicling America snippets |
| `src/archive_detective/` | models, engine, UI, ingest, vision |
| `modal_app.py` | Modal: rank, build packs, eval |
| `scripts/` | fetch, case builder, eval, preprocess |

## Demo cases

Open the Gradio UI, pick a **case file**, read the clipping, inspect evidence cards, follow leads, then **Reveal** for archive facts vs synthetic bridge notes. **Model reading** tab shows the structured clue pack JSON.

## Validate clue packs

```bash
uv run python scripts/preprocess_clue_pack.py data/cases/georgetown_notice.json
```

## License

MIT — newspaper content from LOC Chronicling America (public domain).
