"""Shared Evidence Cabinet skeleton — single source for structure fillers."""

from __future__ import annotations

import re
from typing import Any

CABINET_ARTIFACT_IDS = (
    "clipping_primary",
    "context_index",
    "timeline_note",
    "archivist_bridge",
)

KNOWN_ARTIFACT_IDS = set(CABINET_ARTIFACT_IDS)

DEFAULT_LEADS: list[dict[str, Any]] = [
    {"id": "lead_entities", "label": "Who and what is named?", "unlocks": ["context_index"]},
    {"id": "lead_timeline", "label": "What happened that week?", "unlocks": ["timeline_note"]},
    {"id": "lead_reading", "label": "How should we read this?", "unlocks": ["archivist_bridge"]},
]

WHO_OPTIONS = [
    "a minor figure swept into a larger scandal",
    "a journalist compressing a messy dispatch",
    "a clerk quoting second-hand testimony",
    "an anonymous tip dressed as news copy",
]
WHERE_OPTIONS = [
    "a courthouse corridor",
    "a newspaper city desk",
    "a private meeting room",
    "a public street corner",
]
WHY_OPTIONS = [
    "the printer dropped lines from the metal type",
    "the source demanded anonymity",
    "the editor needed coded language for libel risk",
    "the OCR garbled an ordinary phrase",
]


def _skeleton_artifacts(
    *,
    publication: str,
    date: str,
    citation_url: str,
    raw_ocr: str,
    tagline: str = "",
) -> dict[str, dict[str, Any]]:
    ocr = raw_ocr[:4000]
    return {
        "clipping_primary": {
            "artifact_id": "clipping_primary",
            "kind": "newspaper",
            "title": publication[:72] or "Primary clipping",
            "source": {
                "archive": "Chronicling America",
                "citation_url": citation_url,
                "date": date,
                "publication": publication,
            },
            "media": None,
            "text": {"raw_ocr": ocr, "clean_text": ocr},
            "entities": [],
            "evidence_cards": [
                {
                    "id": "ev_1",
                    "clue_type": "anomaly",
                    "title": "Strange phrasing",
                    "detail": "Something in this clipping refuses to read straight.",
                }
            ],
            "hotspots": [],
        },
        "context_index": {
            "artifact_id": "context_index",
            "kind": "directory",
            "title": "Entity index — archivist extract",
            "source": {
                "archive": "Archivist synthesis from clipping OCR",
                "citation_url": citation_url,
                "date": date,
                "publication": publication,
            },
            "text": {
                "raw_ocr": raw_ocr[:800],
                "clean_text": f"Indexed names and places from the clipping ({publication}, {date}).",
            },
            "entities": [],
            "evidence_cards": [
                {
                    "id": "ev_ctx",
                    "clue_type": "missing_context",
                    "title": "Named figures",
                    "detail": "Who appears in print — and who is conspicuously absent?",
                }
            ],
            "hotspots": [],
        },
        "timeline_note": {
            "artifact_id": "timeline_note",
            "kind": "letter",
            "title": "Timeline note — same week",
            "source": {
                "archive": "Archivist synthesis (synthetic bridge)",
                "citation_url": citation_url,
                "date": date,
                "publication": publication,
            },
            "text": {
                "raw_ocr": f"Date anchor: {date}. Publication: {publication}.",
                "clean_text": (
                    f"The clipping is dated {date}. Whatever happened here sits in the "
                    f"same news cycle as other items from {publication}."
                ),
            },
            "entities": [],
            "evidence_cards": [
                {
                    "id": "ev_time",
                    "clue_type": "time_gap",
                    "title": "Date anchor",
                    "detail": f"The fragment is pinned to {date} — what happened just before or after?",
                }
            ],
            "hotspots": [],
        },
        "archivist_bridge": {
            "artifact_id": "archivist_bridge",
            "kind": "clipping",
            "title": "Archivist margin — reading notes",
            "source": {
                "archive": "Model reading notes (synthetic)",
                "citation_url": citation_url,
                "date": date,
                "publication": publication,
            },
            "text": {
                "raw_ocr": tagline,
                "clean_text": tagline or "The archivist's margin note ties the leads together.",
            },
            "entities": [],
            "evidence_cards": [
                {
                    "id": "ev_bridge",
                    "clue_type": "summary",
                    "title": "Archivist summary",
                    "detail": "A playable reading of the fragment, not a second archive source.",
                }
            ],
            "hotspots": [],
        },
    }


def heuristic_deduction_fields(raw_ocr: str) -> list[dict[str, Any]]:
    """OCR-informed deduction fields for heuristic / skeleton fallback."""
    lower = raw_ocr.lower()
    who_answer = WHO_OPTIONS[1]
    if any(w in lower for w in ("court", "judge", "trial", "verdict")):
        who_answer = WHO_OPTIONS[0]
    elif "?" in raw_ocr or "anonymous" in lower:
        who_answer = WHO_OPTIONS[3]

    where_answer = WHERE_OPTIONS[1]
    if "court" in lower or "county" in lower:
        where_answer = WHERE_OPTIONS[0]

    why_answer = WHY_OPTIONS[1]
    if "?" in raw_ocr:
        why_answer = WHY_OPTIONS[2]
    elif re.search(r"\b\d{4}\b", raw_ocr) and len(raw_ocr) < 120:
        why_answer = WHY_OPTIONS[3]

    return [
        {
            "id": "who",
            "label": "The central figure is probably",
            "answer": who_answer,
            "options": WHO_OPTIONS,
        },
        {
            "id": "where",
            "label": "The key scene most likely occurred at",
            "answer": where_answer,
            "options": WHERE_OPTIONS,
        },
        {
            "id": "why",
            "label": "The odd wording exists because",
            "answer": why_answer,
            "options": WHY_OPTIONS,
        },
    ]


def normalize_cabinet_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Fix lead unlocks and hero id without injecting skeleton artifacts."""
    out = dict(payload)
    out.setdefault("hero_artifact_id", "clipping_primary")

    artifacts: list[dict[str, Any]] = list(out.get("artifacts") or [])
    by_id = {a.get("artifact_id"): dict(a) for a in artifacts if a.get("artifact_id")}

    if "clipping_primary" not in by_id and artifacts:
        hero = dict(artifacts[0])
        hero["artifact_id"] = "clipping_primary"
        by_id["clipping_primary"] = hero

    leads: list[dict[str, Any]] = []
    for i, default in enumerate(DEFAULT_LEADS):
        raw = (out.get("leads") or [])[i] if i < len(out.get("leads") or []) else {}
        unlocks = [u for u in (raw.get("unlocks") or []) if u in KNOWN_ARTIFACT_IDS]
        if not unlocks:
            unlocks = list(default["unlocks"])
        label = str(raw.get("label") or default["label"]).strip() or default["label"]
        leads.append(
            {
                "id": str(raw.get("id") or default["id"]),
                "label": label,
                "unlocks": unlocks,
            }
        )
    out["leads"] = leads
    if by_id:
        out["artifacts"] = list(by_id.values())
    return out


def merge_model_into_skeleton(
    payload: dict[str, Any],
    *,
    publication: str,
    date: str,
    citation_url: str,
    raw_ocr: str,
) -> tuple[dict[str, Any], list[str]]:
    """Model wins on overlap; skeleton fills only missing structure slots."""
    out = normalize_cabinet_payload(payload)
    filled: list[str] = []

    out.setdefault("title", publication[:64] or "Archive fragment")
    out.setdefault("tagline", f"A fragment from {publication} ({date}).")

    skeleton = _skeleton_artifacts(
        publication=publication,
        date=date,
        citation_url=citation_url,
        raw_ocr=raw_ocr,
        tagline=str(out.get("tagline") or ""),
    )

    by_id = {a.get("artifact_id"): dict(a) for a in (out.get("artifacts") or []) if a.get("artifact_id")}
    for aid in CABINET_ARTIFACT_IDS:
        if aid not in by_id:
            by_id[aid] = skeleton[aid]
            filled.append(aid)
    out["artifacts"] = [by_id[aid] for aid in CABINET_ARTIFACT_IDS]

    if len(out.get("leads") or []) < 3:
        out["leads"] = [dict(ld) for ld in DEFAULT_LEADS]
        filled.append("leads")

    sheet = dict(out.get("deduction_sheet") or {})
    fields = list(sheet.get("fields") or [])
    if len(fields) < 3:
        sheet["fields"] = heuristic_deduction_fields(raw_ocr)
        sheet.setdefault("prompt", "Complete the archivist's conclusion before opening the sealed envelope.")
        out["deduction_sheet"] = sheet
        filled.append("deduction_sheet")

    out.setdefault(
        "reveal_notes",
        {
            "direct_archive_facts": [
                f"Publication: {publication}, {date}",
                f"Citation: {citation_url}",
            ],
            "synthetic_bridge_allowed": True,
            "bridge_notes": (
                "Supporting artifacts may be archivist synthesis. "
                "Primary clipping OCR is the direct archive anchor."
            ),
        },
    )
    return out, filled

