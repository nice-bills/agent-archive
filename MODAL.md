# Modal — Archive Detective

Batch jobs for **ingest ranking**, **clue-pack building** (MiniCPM-V on GPU), and **OCR evals**. Uses Modal credits; local fallbacks live in `scripts/` and `src/archive_detective/ingest/`.

## Setup

```bash
uv sync --extra modal
pip install modal  # or: uv pip install modal
modal token new    # one-time auth
```

Optional Hugging Face secret (for gated models / rate limits):

```bash
modal secret create huggingface HF_TOKEN=hf_...
```

## Volume

Data persists on Modal volume `archive-detective-data` mounted at `/data`:

- `/data/raw/` — ingested snippets + `ranked.json`
- `/data/clue_packs/` — generated clue packs
- `/data/eval/` — eval JSON + `summary.md`

Pull results locally (after a run):

```bash
modal volume get archive-detective-data raw/ranked.json data/raw/ranked.json
```

## Commands

```bash
# Fetch ~15 LOC snippets + heuristic rank (CPU, ~5–15 min)
modal run modal_app.py::rank_snippets --target 15

# Top-N clue packs — GPU + MiniCPM when use_model=True
modal run modal_app.py::build_clue_packs --top 5

# Eval: raw OCR vs cleaned pipeline
modal run modal_app.py::run_eval

# Convenience entrypoint
modal run modal_app.py --action rank --target 15
modal run modal_app.py --action packs --top 5
modal run modal_app.py --action eval
```

## Environment variables

| Variable | Where | Purpose |
|----------|--------|---------|
| `ARCHIVE_DETECTIVE_USE_MODEL` | Modal GPU fn / local | `1` enables live MiniCPM-V |
| `ARCHIVE_DETECTIVE_MODEL` | optional | Default `openbmb/MiniCPM-V-4_6` |
| `HF_TOKEN` | Modal secret `huggingface` | Hub auth |

## Local equivalents (no Modal)

```bash
uv run python scripts/fetch_chronicling_america.py --target 15 --rank
uv run python scripts/run_eval_local.py
uv run python scripts/build_cases_from_ingest.py --top 2
```

## Dependencies

Install Modal extras:

```bash
uv sync --extra modal --extra model
```

`model` extra is only needed for local MiniCPM runs; Modal image installs torch/transformers in `modal_app.py`.
