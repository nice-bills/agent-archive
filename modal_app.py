"""
Archive Detective — Modal batch jobs (ranking, clue packs, eval).

Run locally:
  modal run modal_app.py::rank_snippets --target 15
  modal run modal_app.py::build_clue_packs --top 5
  modal run modal_app.py::run_eval
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import modal

APP_NAME = "archive-detective"
ROOT = Path(__file__).resolve().parent

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "httpx>=0.28",
        "pillow>=12.2",
        "pydantic>=2.13",
        "torch>=2.4",
        "transformers>=4.48",
        "accelerate>=1.2",
        "sentencepiece>=0.2",
        "protobuf>=5.0",
    )
    .env({"ARCHIVE_DETECTIVE_USE_MODEL": "1"})
    .add_local_dir(str(ROOT / "src" / "archive_detective"), remote_path="/root/archive_detective")
)

app = modal.App(APP_NAME)
vol = modal.Volume.from_name("archive-detective-data", create_if_missing=True)
DATA_MOUNT = "/data"


def _sync_src():
    import sys

    sys.path.insert(0, "/root")


@app.function(
    image=image,
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
    image=image.gpu("A10G"),
    volumes={DATA_MOUNT: vol},
    timeout=60 * 45,
    memory=16384,
    secrets=[modal.Secret.from_name("huggingface", required=False)],
)
def build_clue_packs(top: int = 5, use_model: bool = True) -> dict:
    """Build clue-pack JSON for top-ranked snippets (MiniCPM on GPU when enabled)."""
    _sync_src()
    from archive_detective.clue_builder import build_clue_pack_from_snippet
    from archive_detective.ingest.ranking import rank_snippets

    raw_dir = Path(DATA_MOUNT) / "raw"
    if not (raw_dir / "manifest.json").is_file():
        fetch_fn = modal.Function.from_name(APP_NAME, "rank_snippets")
        fetch_fn.remote(target=max(top * 3, 15))

    ranked = rank_snippets(raw_dir=raw_dir)
    packs_dir = Path(DATA_MOUNT) / "clue_packs"
    packs_dir.mkdir(parents=True, exist_ok=True)
    built: list[str] = []
    repo_root = Path("/root")

    if use_model:
        os.environ["ARCHIVE_DETECTIVE_USE_MODEL"] = "1"
        from archive_detective import vision

    for row in ranked[:top]:
        vision_payload = None
        img = row.get("image_path")
        if use_model and img:
            full = repo_root / img
            if not full.is_file():
                full = raw_dir.parent.parent / img
            if full.is_file():
                try:
                    vision_payload = vision.extract_clues_from_image(
                        str(full),
                        publication=row.get("publication", ""),
                        date=row.get("date", ""),
                        raw_ocr=row.get("raw_ocr", ""),
                    )
                except Exception:
                    vision_payload = None

        pack = build_clue_pack_from_snippet(row, vision_payload=vision_payload)
        out_path = packs_dir / f"{pack.artifact_id}.json"
        out_path.write_text(pack.model_dump_json(indent=2) + "\n", encoding="utf-8")
        built.append(pack.artifact_id)

    vol.commit()
    return {"built": built, "dir": str(packs_dir)}


@app.function(
    image=image,
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
        print(build_clue_packs.remote(top=top))
    elif action == "eval":
        print(run_eval.remote())
    else:
        raise SystemExit(f"Unknown action: {action}")
