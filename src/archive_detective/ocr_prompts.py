"""Prompts for hosted OCR cleanup / transcription from noisy archive text."""

from __future__ import annotations

OCR_REFINE_SYSTEM = """You are Archive Detective's OCR archivist. You clean noisy Library of Congress newspaper OCR.
Output ONLY valid JSON (no markdown fences):
{
  "raw_ocr": "full transcription — preserve uncertain glyphs, do not invent words",
  "clean_text": "readable version for gameplay",
  "confidence": 0.0
}
Rules:
- Quote only what appears in the noisy OCR input; never add names, dates, or facts not supported by it.
- confidence: 0-1 how complete/readable the source OCR is."""

OCR_REFINE_USER = """Publication: {publication}
Date: {date}

Noisy archive OCR:
{raw_ocr}

Return the JSON object."""


OCR_VISION_SYSTEM = """You transcribe public-domain newspaper clippings from images.
Output ONLY valid JSON (no markdown fences):
{
  "raw_ocr": "verbatim transcription with uncertain letters preserved",
  "clean_text": "readable version for archivists"
}
Rules:
- Transcribe every visible headline and body line you can read.
- Do not invent words absent from the image."""

OCR_VISION_USER = """Publication: {publication}
Date: {date}
Archive hint OCR (may be wrong or incomplete):
{hint_ocr}

Transcribe all visible text from this clipping image. Return the JSON object."""


def build_ocr_vision_prompt(
    *,
    publication: str,
    date: str,
    hint_ocr: str,
) -> tuple[str, str]:
    user = OCR_VISION_USER.format(
        publication=publication,
        date=date,
        hint_ocr=hint_ocr[:3000] or "(none)",
    )
    return OCR_VISION_SYSTEM, user


def build_ocr_refine_prompt(
    *,
    publication: str,
    date: str,
    raw_ocr: str,
) -> tuple[str, str]:
    user = OCR_REFINE_USER.format(
        publication=publication,
        date=date,
        raw_ocr=raw_ocr[:6000],
    )
    return OCR_REFINE_SYSTEM, user
