from __future__ import annotations

from pydantic import BaseModel, Field


class Source(BaseModel):
    archive: str
    citation_url: str
    date: str
    publication: str


class Fragment(BaseModel):
    image_path: str | None = None
    raw_ocr: str
    clean_text: str


class Entity(BaseModel):
    type: str
    value: str


class EvidenceCard(BaseModel):
    id: str
    clue_type: str
    title: str
    detail: str


class LeadOption(BaseModel):
    id: str
    label: str


class RevealNotes(BaseModel):
    direct_archive_facts: list[str] = Field(default_factory=list)
    synthetic_bridge_allowed: bool = True
    bridge_notes: str | None = None


class CluePack(BaseModel):
    artifact_id: str
    source: Source
    fragment: Fragment
    entities: list[Entity]
    evidence_cards: list[EvidenceCard]
    clue_types: list[str]
    mystery_score: float
    lead_options: list[LeadOption]
    reveal_notes: RevealNotes
    beat_intro: str = ""


class CaseDefinition(BaseModel):
    case_id: str
    title: str
    tagline: str
    start_beat: str
    beats: dict[str, CluePack]
    transitions: dict[str, dict[str, str]]
