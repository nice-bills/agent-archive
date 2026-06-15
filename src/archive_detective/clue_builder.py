from __future__ import annotations

import json
import os
import re
from typing import Any

from archive_detective.ingest.ranking import score_snippet
from archive_detective.models import (
    CluePack,
    Entity,
    EvidenceCard,
    Fragment,
    LeadOption,
    RevealNotes,
    Source,
)


def _heuristic_entities(text: str) -> list[Entity]:
    entities: list[Entity] = []
    for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text):
        entities.append(Entity(type="person", value=m.group(1)))
    for m in re.finditer(
        r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
        r"January|February|March|April|May|June|July|August|September|October|November|December)\b",
        text,
    ):
        entities.append(Entity(type="time", value=m.group(1)))
    places = re.findall(
        r"\b([A-Z][a-z]+(?:\s+(?:Street|St\.|Avenue|Ave\.|Road|County|City|Town|District)))\b",
        text,
    )
    for p in places[:4]:
        entities.append(Entity(type="place", value=p))
    # dedupe
    seen: set[tuple[str, str]] = set()
    out: list[Entity] = []
    for e in entities:
        key = (e.type, e.value)
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out[:8]


def _heuristic_evidence(text: str) -> tuple[list[EvidenceCard], list[str]]:
    cards: list[EvidenceCard] = []
    types: list[str] = []
    lower = text.lower()
    if "?" in text:
        cards.append(
            EvidenceCard(
                id="ev_question",
                clue_type="missing_context",
                title="Unanswered question",
                detail="The fragment ends on uncertainty — something was left unsaid in print.",
            )
        )
        types.append("missing_context")
    if any(w in lower for w in ("secret", "anonymous", "cipher", "code", "phrase")):
        cards.append(
            EvidenceCard(
                id="ev_secret",
                clue_type="coded_message",
                title="Secretive wording",
                detail="Language suggests concealed intent rather than open announcement.",
            )
        )
        types.append("coded_message")
    if re.search(r"\b\d{1,2}\s*(?:a\.?m\.?|p\.?m\.?|o'clock|night|midnight)\b", lower):
        cards.append(
            EvidenceCard(
                id="ev_time",
                clue_type="time_gap",
                title="Time-bound detail",
                detail="A specific hour or night window narrows when something could have happened.",
            )
        )
        types.append("time_gap")
    if not cards:
        cards.append(
            EvidenceCard(
                id="ev_fragment",
                clue_type="anomaly",
                title="Strange fragment",
                detail="This clipping stood out in the archive crawl — worth pinning to the board.",
            )
        )
        types.append("anomaly")
    return cards, types


def _clean_text(raw: str) -> str:
    t = re.sub(r"\s+", " ", raw).strip()
    if t:
        t = t[0].upper() + t[1:]
    return t


def build_clue_pack_from_snippet(
    snippet: dict[str, Any],
    *,
    artifact_id: str | None = None,
    vision_payload: dict[str, Any] | None = None,
) -> CluePack:
    """Build a CluePack from raw ingest row + optional MiniCPM JSON."""
    sid = snippet["snippet_id"]
    raw = snippet.get("raw_ocr", "")
    pub = snippet.get("publication", "Unknown newspaper")
    date = snippet.get("date", "unknown")
    citation = snippet.get("citation_url", "https://www.loc.gov/newspapers/")

    if vision_payload and not vision_payload.get("_error"):
        clean = vision_payload.get("clean_text") or _clean_text(raw)
        entities = [
            Entity.model_validate(e) for e in vision_payload.get("entities", [])[:12]
        ]
        cards = []
        for i, c in enumerate(vision_payload.get("evidence_cards", [])[:6]):
            if isinstance(c, dict):
                cards.append(
                    EvidenceCard(
                        id=c.get("id") or f"ev_{i+1}",
                        clue_type=c.get("clue_type") or "anomaly",
                        title=c.get("title") or "Evidence",
                        detail=c.get("detail") or "",
                    )
                )
            else:
                cards.append(EvidenceCard.model_validate(c))
        clue_types = list(vision_payload.get("clue_types", []))[:8]
        leads = []
        for i, o in enumerate(vision_payload.get("lead_options", [])[:4]):
            if isinstance(o, dict):
                oid = o.get("id") or f"lead_{i+1}"
                label = o.get("label") or oid
                leads.append(LeadOption(id=str(oid), label=str(label)))
            else:
                leads.append(LeadOption.model_validate(o))
        if len(leads) < 2:
            for d in (
                LeadOption(id="names", label="Who is named here?"),
                LeadOption(id="place", label="Trace the place"),
                LeadOption(id="close", label="Table this fragment"),
            ):
                if not any(existing.id == d.id for existing in leads):
                    leads.append(d)
                if len(leads) >= 3:
                    break
        beat_intro = vision_payload.get("beat_intro") or (
            f"A fragment from {pub} ({date}) lands on your board."
        )
        mystery = float(vision_payload.get("mystery_score", score_snippet(raw)))
        if not cards or not leads:
            vision_payload = None  # fall through to heuristics
        else:
            if os.environ.get("ARCHIVE_DETECTIVE_USE_LLAMA", "").lower() in {"1", "true", "yes"}:
                extraction_note = "llama.cpp OCR extraction + LOC Chronicling America"
            else:
                extraction_note = "MiniCPM-V structured extraction + LOC OCR"
            return CluePack(
                artifact_id=artifact_id or f"ca_{sid}",
                source=Source(
                    archive="Chronicling America (Library of Congress)",
                    citation_url=citation,
                    date=date,
                    publication=pub,
                ),
                fragment=Fragment(
                    image_path=snippet.get("image_path"),
                    raw_ocr=raw[:6000],
                    clean_text=clean[:6000],
                ),
                entities=entities,
                evidence_cards=cards,
                clue_types=clue_types or ["anomaly"],
                mystery_score=round(min(1.0, max(0.0, mystery)), 3),
                lead_options=leads,
                reveal_notes=RevealNotes(
                    direct_archive_facts=[
                        f"Publication: {pub}, {date}",
                        f"Citation: {citation}",
                        extraction_note,
                    ],
                    synthetic_bridge_allowed=True,
                    bridge_notes="Lead branches may use editorial glue; quoted lines match the fragment.",
                ),
                beat_intro=beat_intro,
            )

    if vision_payload is None or vision_payload.get("_error"):
        clean = _clean_text(raw)
        entities = _heuristic_entities(raw)
        cards, clue_types = _heuristic_evidence(raw)
        leads = [
            LeadOption(id="names", label="Who is named here?"),
            LeadOption(id="place", label="Trace the place"),
            LeadOption(id="close", label="Table this fragment"),
        ]
        beat_intro = f"A clipping from {pub} ({date}) — ink faded, story not."
        mystery = score_snippet(raw, title=snippet.get("title", ""))

    return CluePack(
        artifact_id=artifact_id or f"ca_{sid}",
        source=Source(
            archive="Chronicling America (Library of Congress)",
            citation_url=citation,
            date=date,
            publication=pub,
        ),
        fragment=Fragment(
            image_path=snippet.get("image_path"),
            raw_ocr=raw[:6000],
            clean_text=clean[:6000],
        ),
        entities=entities,
        evidence_cards=cards,
        clue_types=clue_types or ["anomaly"],
        mystery_score=round(min(1.0, max(0.0, mystery)), 3),
        lead_options=leads,
        reveal_notes=RevealNotes(
            direct_archive_facts=[
                f"Publication: {pub}, {date}",
                f"Citation: {citation}",
                "OCR text sourced from LOC Chronicling America ingest",
            ],
            synthetic_bridge_allowed=True,
            bridge_notes="Lead branches may use editorial glue; quoted lines should match the fragment.",
        ),
        beat_intro=beat_intro,
    )


def _repair_truncated_json_object(text: str, start: int) -> dict[str, Any] | None:
    """Best-effort close for MiniCPM outputs cut off mid-object."""
    chunk = text[start:]
    for end in range(len(chunk), 0, -1):
        if chunk[end - 1] not in "}]":
            continue
        candidate = chunk[:end].rstrip().rstrip(",")
        open_brackets = candidate.count("[") - candidate.count("]")
        open_braces = candidate.count("{") - candidate.count("}")
        if open_brackets < 0 or open_braces < 0:
            continue
        repaired = candidate + ("]" * open_brackets) + ("}" * open_braces)
        try:
            payload = json.loads(repaired)
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            continue
    return None


def parse_vision_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    if start < 0:
        raise json.JSONDecodeError("no JSON object", text, 0)
    try:
        payload, _end = json.JSONDecoder().raw_decode(text[start:])
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    repaired = _repair_truncated_json_object(text, start)
    if repaired is not None:
        return repaired
    raise json.JSONDecodeError("no JSON object", text, start)
