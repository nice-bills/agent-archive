from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ArtifactKind = Literal[
    "newspaper",
    "map",
    "letter",
    "photo",
    "object",
    "directory",
    "trial",
    "notice",
    "clipping",
]


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


class ArtifactMedia(BaseModel):
    image_path: str | None = None
    thumb_path: str | None = None


class ArtifactText(BaseModel):
    raw_ocr: str = ""
    clean_text: str = ""


class Artifact(BaseModel):
    artifact_id: str
    kind: str
    title: str
    source: Source
    media: ArtifactMedia | None = None
    text: ArtifactText | None = None
    entities: list[Entity] = Field(default_factory=list)
    evidence_cards: list[EvidenceCard] = Field(default_factory=list)
    hotspots: list[dict] = Field(default_factory=list)


class EvidenceLead(BaseModel):
    id: str
    label: str
    unlocks: list[str] = Field(default_factory=list)


class DeductionField(BaseModel):
    id: str
    label: str
    answer: str
    options: list[str] | None = None


class DeductionSheet(BaseModel):
    prompt: str
    fields: list[DeductionField]


class EvidenceCase(BaseModel):
    case_id: str
    title: str
    tagline: str
    mode: Literal["evidence_cabinet"] = "evidence_cabinet"
    hero_artifact_id: str
    artifacts: list[Artifact]
    leads: list[EvidenceLead]
    deduction_sheet: DeductionSheet
    reveal_notes: RevealNotes
