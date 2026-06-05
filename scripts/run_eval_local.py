#!/usr/bin/env python3
"""Local eval: raw OCR vs cleaned clue-pack pipeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from archive_detective.clue_builder import build_clue_pack_from_snippet
from archive_detective.ingest.ranking import rank_snippets

EVAL_DIR = ROOT / "data" / "eval"


def main() -> None:
    ranked = rank_snippets()[:12]
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for snip in ranked:
        pack = build_clue_pack_from_snippet(snip)
        rows.append(
            {
                "snippet_id": snip["snippet_id"],
                "mystery_score": pack.mystery_score,
                "raw_len": len(snip.get("raw_ocr", "")),
                "clean_len": len(pack.fragment.clean_text),
                "entity_count": len(pack.entities),
                "evidence_count": len(pack.evidence_cards),
            }
        )
    summary = {
        "samples": len(rows),
        "avg_mystery": round(sum(r["mystery_score"] for r in rows) / max(len(rows), 1), 3),
    }
    (EVAL_DIR / "eval.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n",
        encoding="utf-8",
    )
    md = [
        "# Archive Detective eval (local)",
        "",
        f"Samples: **{summary['samples']}** · Avg mystery: **{summary['avg_mystery']}**",
        "",
    ]
    for r in rows:
        md.append(
            f"- `{r['snippet_id']}` — score {r['mystery_score']:.2f}, "
            f"{r['entity_count']} entities, {r['raw_len']}→{r['clean_len']} chars"
        )
    (EVAL_DIR / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {EVAL_DIR / 'eval.json'} and summary.md")


if __name__ == "__main__":
    main()
