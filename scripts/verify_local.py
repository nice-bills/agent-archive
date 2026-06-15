#!/usr/bin/env python3
"""Run local smoke checks before any deploy. Exit 0 only if everything passes.

Covers (library / disk):
  - Case JSON load + evidence-cabinet session rules
  - Gallery clippings + on-disk images (asset_path)
  - Pre-generated case cache validity
  - Live gallery generation (Modal or HF_TOKEN) when configured
  - Live upload generation with pasted OCR when configured
  - Gallery thumb_url paths from gallery_catalog()
  - gr.Server build_server() import

Does NOT cover (gaps — add scripts or manual checks):
  - HTTP serving of /assets/* or /board/* (run server + curl, or capture_demo_screenshots)
  - Browser UI / file picker / drag-drop upload UX
  - Upload without pasted OCR on HF Space (GPU vision can exceed proxy timeouts)
  - Modal cold-start latency, Space queue, or regenerate timeouts
  - Session persistence after Space container restart (upload images are ephemeral)
"""

from __future__ import annotations

import base64
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
from archive_detective.generation import (
    MODEL_REQUIRED_MSG,
    gallery_catalog,
    generate_from_gallery,
    generate_from_upload,
)
from archive_detective.hf_inference import DEFAULT_MODEL, hf_enabled
from archive_detective.modal_play import cabinet_model_label, modal_play_enabled
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


def verify_gallery_thumb_urls() -> None:
    catalog = gallery_catalog()
    if not catalog:
        fail("gallery_catalog() returned no items")
    for item in catalog:
        url = item.get("thumb_url")
        if not url:
            fail(f"gallery {item['id']}: missing thumb_url")
        rel = url.lstrip("/")
        if not asset_path(rel):
            fail(f"gallery {item['id']}: thumb missing on disk: {rel}")
    ok(f"{len(catalog)} gallery thumb URLs resolve on disk")


def verify_upload_validation() -> None:
    try:
        generate_from_upload("", title="x")
        fail("upload: empty image_b64 should raise ValueError")
    except ValueError:
        pass
    ok("upload input validation")


def verify_upload_generation() -> None:
    sample = asset_path("assets/gallery/1919_01_05_resource_sn84026749_1919_01_05_ed_1.jpg")
    if not sample:
        fail("upload smoke: sample gallery image missing")
    data_url = (
        "data:image/jpeg;base64,"
        + base64.b64encode(Path(sample).read_bytes()).decode("ascii")
    )
    verify_upload_validation()
    if not modal_play_enabled() and not hf_enabled():
        ok("upload live generation skipped (no Modal/HF backend)")
        return

    case, meta = generate_from_upload(
        data_url,
        title="verify_local upload smoke",
        raw_ocr="mysterious death actress found poisoned after victory ball",
        regenerate=True,
    )
    expected_source = "live_modal" if modal_play_enabled() else "live"
    if meta.get("source") not in {expected_source, "heuristic"}:
        fail(
            f"upload expected {expected_source!r} or heuristic, got {meta.get('source')!r}"
        )
    hero = next((a for a in case.artifacts if a.artifact_id == case.hero_artifact_id), None)
    if hero and hero.media and hero.media.image_path and not asset_path(hero.media.image_path):
        fail(f"upload case missing hero image: {hero.media.image_path}")
    session = start_evidence_session(case)
    if case.hero_artifact_id not in session.unlocked:
        fail("upload generated case: hero not unlocked")
    ok(f"upload live generation ({meta.get('source')}, {meta.get('ocr_source', 'n/a')})")


def verify_gallery_generation() -> None:
    clippings = load_gallery_catalog()
    if not clippings:
        fail("no gallery clippings")
    if not modal_play_enabled() and not hf_enabled():
        fail(f"gallery generation requires Modal or HF_TOKEN ({MODEL_REQUIRED_MSG})")
    case, meta = generate_from_gallery(clippings[0].id, regenerate=True)
    expected_source = "live_modal" if modal_play_enabled() else "live"
    if meta.get("source") != expected_source:
        fail(
            f"expected {expected_source!r} generation, got {meta.get('source')!r} "
            f"(model={meta.get('model_id')})"
        )
    ocr_source = meta.get("ocr_source")
    if ocr_source not in {"live_refine", "live_vision", "live_vision_modal"}:
        fail(f"expected live OCR, got ocr_source={ocr_source!r}")
    session = start_evidence_session(case)
    if case.hero_artifact_id not in session.unlocked:
        fail("generated case: hero not unlocked")
    cabinet = meta.get("cabinet_model") or meta.get("model_id")
    if modal_play_enabled() and cabinet != cabinet_model_label():
        fail(f"expected cabinet model {cabinet_model_label()}, got {cabinet!r}")
    ok(f"gallery live OCR ({meta.get('ocr_model')}, {ocr_source}) + cabinet ({cabinet})")


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
    verify_gallery_thumb_urls()
    verify_generated_cache()
    verify_gallery_generation()
    verify_upload_generation()

    build_server()
    ok("gr.Server custom board builds")

    print("\nAll local checks passed.")
    print("Start the UI:  uv run python main.py")
    print("Then open:     http://127.0.0.1:7860/")


if __name__ == "__main__":
    main()
