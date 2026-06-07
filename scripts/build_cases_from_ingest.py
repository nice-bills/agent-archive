#!/usr/bin/env python3
"""Build playable case JSON files from ranked Chronicling America snippets."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from archive_detective.clue_builder import build_clue_pack_from_snippet
from archive_detective.llama import extract_clues_from_ocr, llama_enabled, llama_health
from archive_detective.ingest.chronicling_america import RAW_DIR, resolve_snippet_image
from archive_detective.ingest.ranking import rank_snippets
from archive_detective.models import CaseDefinition, CluePack, LeadOption

CASES_DIR = ROOT / "data" / "cases"
ASSETS_DIR = ROOT / "assets"
CLUE_PACKS_DIR = ROOT / "data" / "clue_packs"


def _ensure_leads(pack: CluePack) -> CluePack:
    if len(pack.lead_options) >= 2:
        return pack
    extras = [
        LeadOption(id="names", label="Who is named here?"),
        LeadOption(id="place", label="Trace the place"),
        LeadOption(id="close", label="Table this fragment"),
    ]
    leads = list(pack.lead_options)
    seen = {l.id for l in leads}
    for d in extras:
        if d.id not in seen:
            leads.append(d)
            seen.add(d.id)
        if len(leads) >= 3:
            break
    return pack.model_copy(update={"lead_options": leads})


def _opening_from_clue_pack(snip: dict) -> CluePack | None:
    pack_path = CLUE_PACKS_DIR / f"ca_{snip['snippet_id']}.json"
    if not pack_path.is_file():
        return None
    return _ensure_leads(CluePack.model_validate_json(pack_path.read_text(encoding="utf-8")))


def _closed_beat(open_pack: CluePack) -> CluePack:
    return CluePack(
        artifact_id=f"{open_pack.artifact_id}_closed",
        source=open_pack.source,
        fragment=open_pack.fragment.model_copy(
            update={"image_path": None, "clean_text": "Case tabled. Fragment logged on the board."}
        ),
        entities=[],
        evidence_cards=[
            open_pack.evidence_cards[0].model_copy(
                update={
                    "id": "ev_close",
                    "clue_type": "summary",
                    "title": "Board pinned",
                    "detail": "Enough for tonight — the archive keeps the rest.",
                }
            )
        ]
        if open_pack.evidence_cards
        else [],
        clue_types=["summary"],
        mystery_score=1.0,
        lead_options=[],
        reveal_notes=open_pack.reveal_notes,
        beat_intro="You pin the board shut. The clipping stays real; the rest waits.",
    )


def _llama_payload(snip: dict) -> dict | None:
    if not llama_enabled() or not llama_health():
        return None
    try:
        return extract_clues_from_ocr(
            publication=snip.get("publication", "Unknown"),
            date=snip.get("date", "unknown"),
            raw_ocr=snip.get("raw_ocr", ""),
        )
    except Exception as exc:  # noqa: BLE001 — ingest should fall back to heuristics
        print(f"  llama extraction failed: {exc}")
        return None


def case_from_snippet(snip: dict, case_id: str, title: str, tagline: str) -> CaseDefinition:
    llama = _llama_payload(snip)
    opening = (
        _opening_from_clue_pack(snip)
        or build_clue_pack_from_snippet(snip, vision_payload=llama)
    )
    img_src: Path | None = None
    if opening.fragment.image_path:
        rel = opening.fragment.image_path
        for base in (ROOT, RAW_DIR):
            candidate = base / rel
            if candidate.is_file():
                img_src = candidate
                break
    if img_src is None:
        img_src = resolve_snippet_image(snip, RAW_DIR)
    if img_src and img_src.is_file():
        dest = ASSETS_DIR / f"{case_id}.jpg"
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(img_src, dest)
        opening.fragment.image_path = f"assets/{dest.name}"

    branch_ids = [lead.id for lead in opening.lead_options[:3]]
    beats: dict[str, CluePack] = {"opening": opening}
    transitions: dict[str, dict[str, str]] = {"opening": {}}

    for i, lid in enumerate(branch_ids):
        branch = build_clue_pack_from_snippet(
            snip,
            artifact_id=f"{opening.artifact_id}_{lid}",
            vision_payload=None,
        )
        branch.beat_intro = (
            f"You chase the lead: **{opening.lead_options[i].label}** — "
            "another angle on the same ink-stained fragment."
        )
        branch.fragment.image_path = None
        branch.lead_options = [
            opening.lead_options[(i + 1) % len(opening.lead_options)],
            opening.lead_options[(i + 2) % len(opening.lead_options)],
        ] if len(opening.lead_options) > 1 else []
        if branch.lead_options:
            from archive_detective.models import LeadOption

            branch.lead_options.append(LeadOption(id="close", label="Close the case — for now"))
        beats[lid] = branch
        transitions["opening"][lid] = lid
        transitions[lid] = {"close": "closed"}
        if branch.lead_options:
            for alt in branch.lead_options:
                if alt.id != "close":
                    transitions[lid][alt.id] = alt.id

    beats["closed"] = _closed_beat(opening)
    for bid in branch_ids:
        transitions.setdefault(bid, {})["close"] = "closed"

    return CaseDefinition(
        case_id=case_id,
        title=title,
        tagline=tagline,
        start_beat="opening",
        beats=beats,
        transitions=transitions,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top", type=int, default=3, help="Cases to emit from ranked snippets")
    parser.add_argument("--min-score", type=float, default=0.35)
    args = parser.parse_args()

    ranked = rank_snippets()
    CASES_DIR.mkdir(parents=True, exist_ok=True)

    titles = [
        ("The Midnight Brief", "A night edition column refuses to read like routine news."),
        ("Warehouse Ledger", "Commerce ink hides a sharper question in the margin."),
        ("County Line Report", "A small headline with too many proper nouns."),
    ]

    written = 0
    for snip in ranked:
        if snip.get("mystery_score", 0) < args.min_score:
            continue
        if written >= args.top:
            break
        case_id = f"case_{snip['snippet_id'][:32]}".strip("_")
        title, tagline = titles[written % len(titles)]
        case = case_from_snippet(snip, case_id, title, tagline)
        out = CASES_DIR / f"{case_id}.json"
        out.write_text(case.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {out}")
        written += 1

    print(f"Built {written} cases")


if __name__ == "__main__":
    main()
