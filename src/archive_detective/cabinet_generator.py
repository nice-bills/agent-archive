"""Build and validate Evidence Cabinet cases from clippings or model JSON."""

from __future__ import annotations

import os
from typing import Any, Literal

from archive_detective.cabinet_prompts import build_cabinet_prompt
from archive_detective.clue_builder import build_clue_pack_from_snippet
from archive_detective.gallery import GalleryClipping
from archive_detective.hf_inference import (
    DEFAULT_MODEL,
    chat_completion_json,
    chat_completion_json_with_image,
    hf_enabled,
)
from archive_detective.models import (
    Artifact,
    ArtifactMedia,
    ArtifactText,
    DeductionField,
    DeductionSheet,
    Entity,
    EvidenceCard,
    EvidenceCase,
    EvidenceLead,
    RevealNotes,
    Source,
)

GenerationSource = Literal["cache", "live", "fallback", "heuristic"]


def _validate_case(case: EvidenceCase) -> EvidenceCase:
    if case.mode != "evidence_cabinet":
        raise ValueError("Generated case must be mode evidence_cabinet")
    if len(case.artifacts) < 4:
        raise ValueError("Need at least 4 artifacts")
    if len(case.leads) < 3:
        raise ValueError("Need at least 3 leads")
    if len(case.deduction_sheet.fields) < 3:
        raise ValueError("Need at least 3 deduction fields")
    ids = {a.artifact_id for a in case.artifacts}
    if case.hero_artifact_id not in ids:
        raise ValueError("hero_artifact_id missing from artifacts")
    for lead in case.leads:
        for aid in lead.unlocks:
            if aid not in ids:
                raise ValueError(f"Lead unlocks unknown artifact: {aid}")
    card_count = sum(len(a.evidence_cards) for a in case.artifacts)
    if card_count < 4:
        raise ValueError("Need at least 4 evidence cards total")
    return case


def _apply_clipping_media(case: EvidenceCase, clipping: GalleryClipping) -> EvidenceCase:
    hero = next((a for a in case.artifacts if a.artifact_id == case.hero_artifact_id), None)
    if hero is None:
        hero = case.artifacts[0]
        case = case.model_copy(update={"hero_artifact_id": hero.artifact_id})
    media = ArtifactMedia(
        image_path=clipping.image_path,
        thumb_path=clipping.image_path,
    )
    updated: list[Artifact] = []
    for art in case.artifacts:
        if art.artifact_id == hero.artifact_id:
            updated.append(art.model_copy(update={"media": media}))
        else:
            updated.append(art)
    return case.model_copy(update={"artifacts": updated})


def _case_id_for_clipping(clipping_id: str) -> str:
    return f"generated_{clipping_id}"


def _payload_to_case(
    payload: dict[str, Any],
    *,
    case_id: str,
    clipping: GalleryClipping | None = None,
) -> EvidenceCase:
    payload = dict(payload)
    payload["case_id"] = case_id
    payload["mode"] = "evidence_cabinet"
    if clipping:
        payload.setdefault("title", clipping.headline[:80] or clipping.title[:80])
        payload.setdefault("tagline", f"A fragment from {clipping.publication} ({clipping.date}).")
    case = EvidenceCase.model_validate(payload)
    if clipping:
        case = _apply_clipping_media(case, clipping)
    return _validate_case(case)


def build_heuristic_cabinet(clipping: GalleryClipping) -> EvidenceCase:
    """Deterministic cabinet from OCR heuristics — offline fallback."""
    pack = build_clue_pack_from_snippet(clipping.to_snippet_dict())
    src = pack.source
    hero_id = "clipping_primary"
    cards = pack.evidence_cards[:2] or [
        EvidenceCard(
            id="ev_1",
            clue_type="anomaly",
            title="Strange phrasing",
            detail="Something in this clipping refuses to read straight.",
        )
    ]
    extra_cards = pack.evidence_cards[2:] or [
        EvidenceCard(
            id="ev_2",
            clue_type="missing_context",
            title="Missing context",
            detail="The clipping assumes the reader already knows more than it states.",
        )
    ]

    entities = pack.entities[:8] or [Entity(type="phrase", value="unknown fragment")]
    entity_lines = "; ".join(e.value for e in entities[:6])

    artifacts = [
        Artifact(
            artifact_id=hero_id,
            kind="newspaper",
            title=clipping.headline[:72] or "Primary clipping",
            source=Source(
                archive=src.archive,
                citation_url=src.citation_url,
                date=src.date,
                publication=src.publication,
            ),
            media=ArtifactMedia(
                image_path=clipping.image_path,
                thumb_path=clipping.image_path,
            ),
            text=ArtifactText(
                raw_ocr=pack.fragment.raw_ocr,
                clean_text=pack.fragment.clean_text,
            ),
            entities=entities,
            evidence_cards=cards,
        ),
        Artifact(
            artifact_id="context_index",
            kind="directory",
            title="Entity index — archivist extract",
            source=Source(
                archive="Archivist synthesis from clipping OCR",
                citation_url=src.citation_url,
                date=src.date,
                publication=src.publication,
            ),
            text=ArtifactText(
                raw_ocr=entity_lines,
                clean_text=f"Indexed from the clipping: {entity_lines}",
            ),
            entities=entities,
            evidence_cards=extra_cards[:1],
        ),
        Artifact(
            artifact_id="timeline_note",
            kind="letter",
            title="Timeline note — same week",
            source=Source(
                archive="Archivist synthesis (synthetic bridge)",
                citation_url=src.citation_url,
                date=src.date,
                publication=src.publication,
            ),
            text=ArtifactText(
                raw_ocr=f"Date anchor: {src.date}. Publication: {src.publication}.",
                clean_text=(
                    f"The clipping is dated {src.date}. Whatever happened here sits in the "
                    f"same news cycle as other items from {src.publication}."
                ),
            ),
            evidence_cards=[
                EvidenceCard(
                    id="ev_time",
                    clue_type="time_gap",
                    title="Date anchor",
                    detail=f"The fragment is pinned to {src.date} — what happened just before or after?",
                )
            ],
        ),
        Artifact(
            artifact_id="archivist_bridge",
            kind="clipping",
            title="Archivist margin — reading notes",
            source=Source(
                archive="Model/heuristic reading notes (synthetic)",
                citation_url=src.citation_url,
                date=src.date,
                publication=src.publication,
            ),
            text=ArtifactText(
                raw_ocr=pack.beat_intro,
                clean_text=pack.beat_intro or "The archivist's margin note ties the leads together.",
            ),
            evidence_cards=[
                EvidenceCard(
                    id="ev_bridge",
                    clue_type="summary",
                    title="Archivist summary",
                    detail=pack.beat_intro or "A playable reading of the fragment, not a second archive source.",
                )
            ],
        ),
    ]

    leads = [
        EvidenceLead(id="lead_entities", label="Who and what is named?", unlocks=["context_index"]),
        EvidenceLead(id="lead_timeline", label="What happened that week?", unlocks=["timeline_note"]),
        EvidenceLead(id="lead_reading", label="How should we read this?", unlocks=["archivist_bridge"]),
    ]

    lead_labels = [l.label for l in pack.lead_options[:3]]
    if lead_labels:
        for i, label in enumerate(lead_labels):
            if i < len(leads):
                leads[i] = leads[i].model_copy(update={"label": label})

    who_opts = [
        "a minor figure swept into a larger scandal",
        "a journalist compressing a messy dispatch",
        "a clerk quoting second-hand testimony",
        "an anonymous tip dressed as news copy",
    ]
    where_opts = [
        "a courthouse corridor",
        "a newspaper city desk",
        "a private meeting room",
        "a public street corner",
    ]
    why_opts = [
        "the printer dropped lines from the metal type",
        "the source demanded anonymity",
        "the editor needed coded language for libel risk",
        "the OCR garbled an ordinary phrase",
    ]

    case = EvidenceCase(
        case_id=_case_id_for_clipping(clipping.id),
        title=(clipping.headline[:64] or clipping.title[:64] or "Generated Case"),
        tagline=pack.beat_intro or f"A fragment from {clipping.publication}, {clipping.date}.",
        hero_artifact_id=hero_id,
        artifacts=artifacts,
        leads=leads,
        deduction_sheet=DeductionSheet(
            prompt="Complete the archivist's conclusion before opening the sealed envelope.",
            fields=[
                DeductionField(id="who", label="The central figure is probably", answer=who_opts[0], options=who_opts),
                DeductionField(
                    id="where",
                    label="The key scene most likely occurred at",
                    answer=where_opts[1],
                    options=where_opts,
                ),
                DeductionField(
                    id="why",
                    label="The odd wording exists because",
                    answer=why_opts[1],
                    options=why_opts,
                ),
            ],
        ),
        reveal_notes=RevealNotes(
            direct_archive_facts=[
                f"Publication: {src.publication}, {src.date}",
                f"Citation: {src.citation_url}",
                "Quoted lines in the primary clipping match bundled LOC OCR.",
            ],
            synthetic_bridge_allowed=True,
            bridge_notes=(
                "Supporting artifacts are archivist synthesis for gameplay. "
                "Only the primary clipping image and OCR are direct archive material."
            ),
        ),
    )
    return _validate_case(case)


def generate_cabinet_from_clipping(
    clipping: GalleryClipping,
    *,
    force_live: bool = False,
    model_id: str | None = None,
) -> tuple[EvidenceCase, GenerationSource, str]:
    """Generate case via HF (if enabled) or heuristic fallback."""
    model = model_id or os.environ.get("ARCHIVE_DETECTIVE_HF_MODEL", DEFAULT_MODEL)
    case_id = _case_id_for_clipping(clipping.id)

    if hf_enabled() and (force_live or os.environ.get("ARCHIVE_DETECTIVE_PREFER_LIVE", "").lower() in {"1", "true", "yes"}):
        system, user = build_cabinet_prompt(
            publication=clipping.publication,
            date=clipping.date,
            citation_url=clipping.citation_url,
            raw_ocr=clipping.raw_ocr,
            mystery_score=clipping.mystery_score,
        )
        try:
            if clipping.image_url:
                payload = chat_completion_json_with_image(
                    system=system,
                    user=user,
                    image_url=clipping.image_url,
                    model=model,
                )
            else:
                payload = chat_completion_json(system=system, user=user, model=model)
            case = _payload_to_case(payload, case_id=case_id, clipping=clipping)
            return case, "live", model
        except Exception:
            pass

    case = build_heuristic_cabinet(clipping)
    return case, "heuristic", "heuristic"


def generate_cabinet_from_upload(
    *,
    title: str,
    raw_ocr: str,
    image_path: str,
    citation_url: str = "",
    publication: str = "Uploaded clipping",
    date: str = "unknown",
    force_live: bool = False,
    model_id: str | None = None,
) -> tuple[EvidenceCase, GenerationSource, str]:
    clipping = GalleryClipping(
        id=f"upload_{title[:24]}",
        headline=title,
        title=title,
        date=date,
        publication=publication,
        citation_url=citation_url or "https://www.loc.gov/",
        raw_ocr=raw_ocr,
        image_path=image_path,
        image_url="",
        mystery_score=0.5,
    )
    case, source, model = generate_cabinet_from_clipping(
        clipping, force_live=force_live, model_id=model_id
    )
    upload_case_id = f"generated_upload_{clipping.id}"
    return case.model_copy(update={"case_id": upload_case_id}), source, model
