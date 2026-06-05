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

Playable micro-mystery machine built from **public-domain newspaper fragments**. A small multimodal model reads noisy clippings, extracts entities and clue types, and turns fragments into short interactive cases — not an archive chatbot.

**Hackathon track:** Adventure in Thousand Token Wood · **Model story:** MiniCPM-V 4.6 (OCR + clue extraction) · **Modal:** preprocessing / eval (planned)

## Local development

```bash
cd archive-detective
uv sync
uv run python scripts/generate_artifact.py   # demo clipping image
uv run python main.py                        # http://127.0.0.1:7860
```

## Project layout

- `app.py` — Gradio app for Hugging Face Spaces
- `data/cases/` — JSON clue-pack case definitions
- `src/archive_detective/` — models, case loader, game engine, UI
- `scripts/` — artifact image generator, future Chronicling America ingest

## Demo case

Open **The Hart Notice** (`georgetown_notice`): read the clipping, inspect evidence cards, pick a lead, then use **Reveal** to see archive-grounded facts vs synthetic bridge notes.
