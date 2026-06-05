from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw"
RANKED_PATH = RAW_DIR / "ranked.json"

MYSTERY_KEYWORDS = (
    "secret",
    "mystery",
    "missing",
    "murder",
    "robbery",
    "arrest",
    "escaped",
    "anonymous",
    "strange",
    "disappear",
    "body",
    "poison",
    "confess",
    "midnight",
    "disguise",
    "cipher",
    "ransom",
    "whisper",
    "suspect",
    "alibi",
)

NOISE_PATTERNS = (
    r"\bPAGE\s+\d+",
    r"^\s*ADVERTISEMENT",
    r"SUBSCRIBE\s+NOW",
    r"ALL\s+RIGHTS",
)


def score_snippet(raw_ocr: str, *, title: str = "") -> float:
    """Heuristic mystery_score in [0, 1] — fast local fallback for Modal."""
    text = f"{title} {raw_ocr}".lower()
    if len(text.strip()) < 30:
        return 0.05

    score = 0.25
    hits = sum(1 for kw in MYSTERY_KEYWORDS if kw in text)
    score += min(0.45, hits * 0.08)

    # Proper nouns / places hint at narrative
    caps = re.findall(r"\b[A-Z][a-z]{2,}\b", raw_ocr)
    score += min(0.15, len(set(caps)) * 0.02)

    # OCR noise can be interesting but penalize extreme garbage
    weird = len(re.findall(r"[^a-zA-Z0-9\s.,;:'\"-]", raw_ocr))
    ratio = weird / max(len(raw_ocr), 1)
    if ratio > 0.12:
        score -= 0.1
    elif ratio > 0.05:
        score += 0.05

    for pat in NOISE_PATTERNS:
        if re.search(pat, raw_ocr, re.I):
            score -= 0.12

    # Length sweet spot
    n = len(raw_ocr)
    if 120 <= n <= 1200:
        score += 0.12
    elif n < 80:
        score -= 0.15

    # Questions and time cues
    if "?" in raw_ocr:
        score += 0.06
    if re.search(r"\b\d{1,2}\s*(?:a\.?m\.?|p\.?m\.?|o'clock)\b", text):
        score += 0.05

    return round(max(0.0, min(1.0, score)), 3)


def rank_snippets(
    snippets: list[dict[str, Any]] | None = None,
    *,
    raw_dir: Path | None = None,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    from archive_detective.ingest.chronicling_america import load_raw_manifest

    from archive_detective.debug_log import debug_log
    from archive_detective.ingest.chronicling_america import discover_snippets_on_disk

    rows = snippets if snippets is not None else load_raw_manifest(raw_dir)
    out_dir = raw_dir or RAW_DIR
    disk_count = len(discover_snippets_on_disk(out_dir))
    # #region agent log
    debug_log(
        "ranking.py:rank_snippets:entry",
        "rank_start",
        {"rows_in": len(rows), "disk_snippet_files": disk_count},
        "H3",
    )
    # #endregion
    ranked: list[dict[str, Any]] = []
    for row in rows:
        ms = score_snippet(row.get("raw_ocr", ""), title=row.get("title", ""))
        ranked.append({**row, "mystery_score": ms})
    ranked.sort(key=lambda r: r["mystery_score"], reverse=True)
    if top_n:
        ranked = ranked[:top_n]

    out_dir.mkdir(parents=True, exist_ok=True)
    if ranked or disk_count == 0:
        (out_dir / "ranked.json").write_text(
            json.dumps({"snippets": ranked}, indent=2) + "\n",
            encoding="utf-8",
        )
    # #region agent log
    debug_log(
        "ranking.py:rank_snippets:exit",
        "rank_done",
        {"ranked": len(ranked), "wrote_ranked": bool(ranked or disk_count == 0)},
        "H3",
    )
    # #endregion
    return ranked
