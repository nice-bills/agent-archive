"""
Archive Detective — Modal CPU batch jobs (ranking, eval).

Run locally:
  modal run modal_app.py::rank_snippets --target 15
  modal run modal_app.py::run_eval
  modal run modal_gpu.py::build_clue_packs --top 5   # GPU — see modal_gpu.py
"""

from __future__ import annotations

import json
from pathlib import Path

import modal

APP_NAME = "archive-detective"
ROOT = Path(__file__).resolve().parent

app = modal.App(APP_NAME)
vol = modal.Volume.from_name("archive-detective-data", create_if_missing=True)
DATA_MOUNT = "/data"

# CPU jobs must not require a Modal "huggingface" secret at deploy time.
cpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("httpx>=0.28", "pillow>=12.2", "pydantic>=2.13")
    .add_local_dir(str(ROOT / "src" / "archive_detective"), remote_path="/root/archive_detective")
)

def _sync_src():
    import sys

    sys.path.insert(0, "/root")


@app.function(
    image=cpu_image,
    volumes={DATA_MOUNT: vol},
    timeout=60 * 20,
    memory=2048,
)
def rank_snippets(target: int = 20, per_query: int = 5) -> dict:
    """Fetch + heuristic-rank Chronicling America fragments."""
    _sync_src()
    from archive_detective.ingest.chronicling_america import fetch_snippets
    from archive_detective.ingest.ranking import rank_snippets as rank_local

    out = Path(DATA_MOUNT) / "raw"
    snippets = fetch_snippets(
        target=target,
        per_query=per_query,
        out_dir=out,
        download_images=True,
    )
    ranked = rank_local(raw_dir=out)
    vol.commit()
    return {"fetched": len(snippets), "ranked": len(ranked), "top": ranked[:5]}


@app.function(
    image=cpu_image,
    volumes={DATA_MOUNT: vol},
    timeout=60 * 15,
    memory=2048,
)
def run_eval(sample: int = 8) -> dict:
    """Compare raw OCR vs heuristic clean vs clue-pack pipeline."""
    _sync_src()
    from archive_detective.clue_builder import build_clue_pack_from_snippet
    from archive_detective.ingest.chronicling_america import load_raw_manifest
    from archive_detective.ingest.ranking import rank_snippets

    raw_dir = Path(DATA_MOUNT) / "raw"
    ranked = rank_snippets(raw_dir=raw_dir)[:sample]
    eval_dir = Path(DATA_MOUNT) / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for snip in ranked:
        pack = build_clue_pack_from_snippet(snip)
        raw = snip.get("raw_ocr", "")
        clean = pack.fragment.clean_text
        rows.append(
            {
                "snippet_id": snip["snippet_id"],
                "mystery_score": pack.mystery_score,
                "raw_len": len(raw),
                "clean_len": len(clean),
                "entity_count": len(pack.entities),
                "evidence_count": len(pack.evidence_cards),
                "raw_preview": raw[:240],
                "clean_preview": clean[:240],
            }
        )

    summary = {
        "samples": len(rows),
        "avg_mystery": round(sum(r["mystery_score"] for r in rows) / max(len(rows), 1), 3),
        "avg_entities": round(sum(r["entity_count"] for r in rows) / max(len(rows), 1), 2),
    }
    payload = {"summary": summary, "rows": rows}
    (eval_dir / "eval.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    md_lines = [
        "# Archive Detective — OCR / clue-pack eval",
        "",
        f"- Samples: **{summary['samples']}**",
        f"- Avg mystery score: **{summary['avg_mystery']}**",
        f"- Avg entities per pack: **{summary['avg_entities']}**",
        "",
        "| snippet | mystery | entities | raw → clean |",
        "|---|---:|---:|---|",
    ]
    for r in rows:
        md_lines.append(
            f"| `{r['snippet_id'][:24]}…` | {r['mystery_score']:.2f} | "
            f"{r['entity_count']} | {r['raw_len']} → {r['clean_len']} |"
        )
    (eval_dir / "summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    vol.commit()
    return {"summary": summary, "eval_dir": str(eval_dir)}


@app.local_entrypoint()
def main(action: str = "rank", target: int = 15, top: int = 5) -> None:
    if action == "rank":
        print(rank_snippets.remote(target=target))
    elif action == "packs":
        fn = modal.Function.from_name("archive-detective-gpu", "build_clue_packs")
        print(fn.remote(top=top))
    elif action == "eval":
        print(run_eval.remote())
    else:
        raise SystemExit(f"Unknown action: {action}")
