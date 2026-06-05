"""Prompt templates for MiniCPM-V clue extraction."""

from __future__ import annotations

CLUE_EXTRACTION_SYSTEM = """You are Archive Detective — a forensic reader of public-domain newspaper clippings.
Read the image and OCR text. Output ONLY valid JSON matching this schema (no markdown fences):
{
  "clean_text": "readable transcription",
  "entities": [{"type": "person|place|org|time|object|phrase", "value": "..."}],
  "evidence_cards": [
    {"id": "ev_1", "clue_type": "coded_message|missing_context|time_gap|motive|anomaly|place|summary", "title": "...", "detail": "..."}
  ],
  "clue_types": ["..."],
  "mystery_score": 0.0,
  "lead_options": [{"id": "lead_1", "label": "Short player-facing question"}],
  "beat_intro": "One atmospheric sentence for the detective board"
}
Rules:
- Quote only what you can see; do not invent facts beyond reasonable OCR cleanup.
- mystery_score: 0-1 how playable/mysterious this fragment is.
- 2-4 evidence_cards, 2-3 lead_options max.
- Keep titles under 8 words."""

CLUE_EXTRACTION_USER = """Publication: {publication}
Date: {date}
Archive OCR (noisy):
{raw_ocr}

Analyze this clipping and return the JSON object."""


def build_extraction_prompt(
    *,
    publication: str,
    date: str,
    raw_ocr: str,
) -> tuple[str, str]:
    user = CLUE_EXTRACTION_USER.format(
        publication=publication,
        date=date,
        raw_ocr=raw_ocr[:4000],
    )
    return CLUE_EXTRACTION_SYSTEM, user
