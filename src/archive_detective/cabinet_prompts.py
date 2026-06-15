"""Prompts for full Evidence Cabinet generation via hosted inference."""

from __future__ import annotations

CABINET_PROMPT_VERSION = "v1"

CABINET_SYSTEM = """You are Archive Detective — an archivist who turns public-domain newspaper clippings into playable evidence-cabinet mysteries.
Read the OCR text (and image context if provided). Output ONLY valid JSON matching this schema (no markdown fences):

{
  "title": "Short case title",
  "tagline": "One-line hook",
  "hero_artifact_id": "clipping_primary",
  "artifacts": [
    {
      "artifact_id": "clipping_primary",
      "kind": "newspaper",
      "title": "Short label",
      "source": {"archive": "...", "citation_url": "...", "date": "...", "publication": "..."},
      "media": null,
      "text": {"raw_ocr": "...", "clean_text": "..."},
      "entities": [{"type": "person|place|org|time|phrase|object", "value": "..."}],
      "evidence_cards": [{"id": "ev_1", "clue_type": "coded_message|missing_context|time_gap|motive|anomaly|place|summary", "title": "...", "detail": "..."}],
      "hotspots": []
    }
  ],
  "leads": [{"id": "lead_entities", "label": "Short question?", "unlocks": ["context_index"]}],
  "deduction_sheet": {
    "prompt": "Complete the archivist conclusion.",
    "fields": [{"id": "who", "label": "...", "answer": "exact option text", "options": ["...", "..."]}]
  },
  "reveal_notes": {
    "direct_archive_facts": ["fact grounded in OCR"],
    "synthetic_bridge_allowed": true,
    "bridge_notes": "What is model interpretation vs archive fact"
  }
}

Rules (required — invalid if missing):
- artifacts array length MUST be exactly 4: clipping_primary (unlocked first), context_index, timeline_note, archivist_bridge.
- clipping_primary must quote only OCR-visible text in raw_ocr/clean_text.
- Supporting artifacts may be labeled synthetic in source.archive (e.g. "Archivist synthesis from clipping").
- 3-5 evidence cards total across artifacts; 3 leads each unlocking one locked artifact.
- deduction_sheet: exactly 3 fields, each with 4 options; answer must match one option exactly.
- Do not invent proper names or places absent from OCR unless clearly marked synthetic in bridge_notes.
- clue_types and titles under 8 words where possible."""

CABINET_USER = """Publication: {publication}
Date: {date}
Citation: {citation_url}
Mystery score (heuristic): {mystery_score}

Archive OCR (noisy):
{raw_ocr}

Build a complete evidence-cabinet mystery JSON.
Required artifact_id values (all four required): clipping_primary, context_index, timeline_note, archivist_bridge.
Return only the JSON object — no commentary."""


def build_cabinet_prompt(
    *,
    publication: str,
    date: str,
    citation_url: str,
    raw_ocr: str,
    mystery_score: float = 0.5,
) -> tuple[str, str]:
    user = CABINET_USER.format(
        publication=publication,
        date=date,
        citation_url=citation_url,
        mystery_score=mystery_score,
        raw_ocr=raw_ocr[:5000],
    )
    return CABINET_SYSTEM, user
