#!/usr/bin/env python3
"""Run local smoke checks before any deploy. Exit 0 only if everything passes."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from archive_detective.cases import (
    asset_path,
    case_mode,
    list_cases,
    load_case,
    load_evidence_case,
)
from archive_detective.engine import start_session, resolve_image
from archive_detective.evidence_engine import start_evidence_session
from archive_detective.ingest.ranking import rank_snippets
from archive_detective.gallery import load_gallery_catalog
from archive_detective.generated_cache import list_cached_cases, load_cached_case
from archive_detective.generation import generate_from_gallery
from archive_detective.server_app import build_server


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def fail(msg: str) -> None:
    print(f"  ✗ {msg}")
    raise SystemExit(1)


def verify_beat_case(case_id: str) -> None:
    case = load_case(case_id)
    session = start_session(case_id)
    img = resolve_image(session.pack)
    if session.pack.fragment.image_path and not img:
        fail(f"{case_id}: missing image {session.pack.fragment.image_path}")
    if not session.pack.lead_options:
        fail(f"{case_id}: opening beat has no leads")
    if not session.pack.evidence_cards:
        fail(f"{case_id}: opening beat has no evidence cards")
    first = session.pack.lead_options[0]
    nxt = session.choose_lead(first.id)
    if nxt and nxt not in case.beats:
        fail(f"{case_id}: transition to unknown beat {nxt!r}")
    ok(f"{case_id} ({case.title})")


def verify_evidence_case(case_id: str) -> None:
    case = load_evidence_case(case_id)
    if case.mode != "evidence_cabinet":
        fail(f"{case_id}: expected mode evidence_cabinet")
    if len(case.artifacts) < 4:
        fail(f"{case_id}: need at least 4 artifacts")
    card_count = sum(len(a.evidence_cards) for a in case.artifacts)
    if card_count < 6:
        fail(f"{case_id}: need at least 6 evidence cards (has {card_count})")
    if len(case.leads) < 3:
        fail(f"{case_id}: need at least 3 leads")
    if len(case.deduction_sheet.fields) < 3:
        fail(f"{case_id}: need at least 3 deduction fields")

    hero = next((a for a in case.artifacts if a.artifact_id == case.hero_artifact_id), None)
    if hero is None:
        fail(f"{case_id}: hero_artifact_id not found")

    for art in case.artifacts:
        if art.media and art.media.image_path:
            if not asset_path(art.media.image_path):
                fail(f"{case_id}: missing image {art.media.image_path}")
        if not art.source.citation_url:
            fail(f"{case_id}: artifact {art.artifact_id} missing citation_url")

    session = start_evidence_session(case)
    if case.hero_artifact_id not in session.unlocked:
        fail(f"{case_id}: hero artifact not unlocked at start")

    first_lead = case.leads[0]
    session.choose_lead(first_lead.id)
    for aid in first_lead.unlocks:
        if aid not in session.unlocked:
            fail(f"{case_id}: lead {first_lead.id} did not unlock {aid}")

    needle = "Hart" if case_id == "hart_notice_evidence_cabinet" else "the"
    session.search(needle)
    if not session.search_matches:
        fail(f"{case_id}: search for {needle!r} returned no matches")

    answers = {field.id: field.answer for field in case.deduction_sheet.fields}
    result = session.submit_deduction(answers)
    if not result.get("all_correct"):
        fail(f"{case_id}: deduction validation failed for correct answers")

    ok(f"{case_id} ({case.title}) [evidence cabinet]")


def verify_gallery() -> None:
    clippings = load_gallery_catalog()
    if len(clippings) < 10:
        fail(f"gallery needs at least 10 clippings (has {len(clippings)})")
    ok(f"{len(clippings)} gallery clippings")
    for clip in clippings:
        if not asset_path(clip.image_path):
            fail(f"gallery missing image: {clip.image_path}")
    ok("gallery images on disk")


def verify_generated_cache() -> None:
    cached = list_cached_cases()
    if len(cached) < 10:
        fail(f"need cached generated cases for gallery (has {len(cached)})")
    ok(f"{len(cached)} cached generated cases")
    for path in cached[:3]:
        case = load_cached_case(path)
        if case is None:
            fail(f"invalid cached case: {path.name}")
        if len(case.artifacts) < 4:
            fail(f"{path.name}: need 4 artifacts")
    ok("cached generated cases validate")


def verify_gallery_generation() -> None:
    clippings = load_gallery_catalog()
    if not clippings:
        fail("no gallery clippings")
    case, meta = generate_from_gallery(clippings[0].id, regenerate=False)
    if meta.get("source") not in {"cache", "heuristic", "fallback", "live"}:
        fail(f"unexpected generation source: {meta.get('source')}")
    session = start_evidence_session(case)
    if case.hero_artifact_id not in session.unlocked:
        fail("generated case: hero not unlocked")
    ok(f"gallery generate path ({meta.get('source')})")


def main() -> None:
    print("Archive Detective — local verification\n")

    cases = list_cases()
    if not cases:
        fail("no cases in data/cases/")
    ok(f"{len(cases)} case files")

    evidence_cases = [cid for cid in cases if case_mode(cid) == "evidence_cabinet"]
    if not evidence_cases:
        fail("no evidence-cabinet case found — add hart_notice_evidence_cabinet.json")
    ok(f"{len(evidence_cases)} evidence-cabinet case(s)")

    for case_id in cases:
        if case_mode(case_id) == "evidence_cabinet":
            verify_evidence_case(case_id)
        else:
            verify_beat_case(case_id)

    ranked = rank_snippets()
    if not ranked:
        fail("ranked.json empty — run fetch or seed data/raw/")
    ok(f"{len(ranked)} ranked snippets")

    verify_gallery()
    verify_generated_cache()
    verify_gallery_generation()

    build_server()
    ok("gr.Server custom board builds")

    print("\nAll local checks passed.")
    print("Start the UI:  uv run python main.py")
    print("Then open:     http://127.0.0.1:7860/")


if __name__ == "__main__":
    main()
