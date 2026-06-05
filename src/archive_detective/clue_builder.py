from __future__ import annotations

import json
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

    if vision_payload:
        clean = vision_payload.get("clean_text") or _clean_text(raw)
        entities = [
            Entity.model_validate(e) for e in vision_payload.get("entities", [])[:12]
        ]
        cards = [
            EvidenceCard.model_validate(c)
            for c in vision_payload.get("evidence_cards", [])[:6]
        ]
        clue_types = list(vision_payload.get("clue_types", []))[:8]
        leads = [
            LeadOption.model_validate(o)
            for o in vision_payload.get("lead_options", [])[:4]
        ]
        beat_intro = vision_payload.get("beat_intro") or (
            f"A fragment from {pub} ({date}) lands on your board."
        )
        mystery = float(vision_payload.get("mystery_score", score_snippet(raw)))
    else:
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


def parse_vision_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)
