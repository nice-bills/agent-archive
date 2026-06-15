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
# Fetch + rank (CPU). LOC may fail from Modal cloud — existing volume snippets are still ranked.
uv run modal run modal_app.py --action rank --target 15

# Re-score only (no LOC fetch)
uv run modal run modal_app.py --action rank-only

# Upload local data/raw first if volume is empty
./scripts/run_modal.sh seed

# Top-N clue packs — GPU + MiniCPM when use_model=True
modal run modal_gpu.py::build_clue_packs --top 5

# Deploy play-time GPU (one job: MiniCPM-V OCR → MiniCPM5-1B cabinet)
./scripts/deploy_modal_gpu.sh

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
| `ARCHIVE_DETECTIVE_MODAL_PLAY` | Space / local | `auto` (default), `1`, or `0` — one GPU job per gallery/upload pick |
| `ARCHIVE_DETECTIVE_MODEL` | optional | Default `openbmb/MiniCPM-V-4.6` |
| `ARCHIVE_DETECTIVE_TEXT_MODEL` | optional | Default `openbmb/MiniCPM5-1B` |
| `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` | HF Space secrets | Call deployed `generate_case_play` from CPU Space |
| `HF_TOKEN` | Modal secret `huggingface` | Hub auth + weights download |

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

`model` extra is only needed for local MiniCPM runs; Modal image installs torch/transformers in `modal_gpu.py`.

## Play-time generation (gallery / upload)

1. Deploy: `./scripts/deploy_modal_gpu.sh` → `archive-detective-gpu::generate_case_play`
2. Local or HF Space: set `MODAL_TOKEN_ID` + `MODAL_TOKEN_SECRET` (or `modal token new` locally)
3. `ARCHIVE_DETECTIVE_MODAL_PLAY=auto` (default) — each polaroid pick runs **one A10G job**: MiniCPM-V OCR → unload → MiniCPM5-1B cabinet JSON

Cold start: first pick after idle may take several minutes (model downloads + load). `max_containers=1` avoids parallel GPU burn. Container scales down after ~60s idle (`scaledown_window=60`).
