"""Session engine for evidence-cabinet cases."""

from __future__ import annotations

from dataclasses import dataclass, field

from archive_detective.cases import asset_path
from archive_detective.models import Artifact, EvidenceCase, RevealNotes


@dataclass
class EvidenceSession:
    case: EvidenceCase
    unlocked: set[str] = field(default_factory=set)
    selected_artifact_id: str = ""
    followed_leads: list[str] = field(default_factory=list)
    search_query: str = ""
    search_matches: list[str] = field(default_factory=list)
    pinned_cards: set[str] = field(default_factory=set)
    deduction_answers: dict[str, str] = field(default_factory=dict)
    deduction_result: dict | None = None
    revealed: bool = False

    def __post_init__(self) -> None:
        if not self.unlocked:
            self.unlocked = {self.case.hero_artifact_id}
        if not self.selected_artifact_id:
            self.selected_artifact_id = self.case.hero_artifact_id

    @property
    def selected_artifact(self) -> Artifact:
        for art in self.case.artifacts:
            if art.artifact_id == self.selected_artifact_id:
                return art
        return self.case.artifacts[0]

    def artifact_by_id(self, artifact_id: str) -> Artifact | None:
        return next((a for a in self.case.artifacts if a.artifact_id == artifact_id), None)

    def select_artifact(self, artifact_id: str) -> bool:
        if artifact_id not in self.unlocked:
            return False
        if not self.artifact_by_id(artifact_id):
            return False
        self.selected_artifact_id = artifact_id
        return True

    def choose_lead(self, lead_id: str) -> bool:
        lead = next((item for item in self.case.leads if item.id == lead_id), None)
        if lead is None:
            return False
        for aid in lead.unlocks:
            self.unlocked.add(aid)
        if lead.unlocks:
            self.selected_artifact_id = lead.unlocks[0]
        if lead_id not in self.followed_leads:
            self.followed_leads.append(lead_id)
        return True

    def search(self, query: str) -> dict[str, object]:
        self.search_query = query.strip()
        self.search_matches = []
        if not self.search_query:
            return {"query": "", "matches": [], "count": 0}

        needle = self.search_query.lower()
        for art in self.case.artifacts:
            if art.artifact_id not in self.unlocked:
                continue
            corpus: list[str] = [art.title]
            if art.text:
                corpus.extend([art.text.raw_ocr, art.text.clean_text])
            corpus.extend(entity.value for entity in art.entities)
            if needle in " ".join(corpus).lower():
                self.search_matches.append(art.artifact_id)
        return {
            "query": self.search_query,
            "matches": list(self.search_matches),
            "count": len(self.search_matches),
        }

    def submit_deduction(self, answers: dict[str, str]) -> dict:
        self.deduction_answers = {k: str(v).strip() for k, v in answers.items()}
        field_results: list[dict] = []
        all_correct = True
        for sheet_field in self.case.deduction_sheet.fields:
            given = self.deduction_answers.get(sheet_field.id, "")
            expected = sheet_field.answer.strip()
            correct = given.lower() == expected.lower()
            field_results.append(
                {
                    "field_id": sheet_field.id,
                    "label": sheet_field.label,
                    "correct": correct,
                    "given": given,
                    "expected": expected,
                }
            )
            if not correct:
                all_correct = False
        self.deduction_result = {"all_correct": all_correct, "fields": field_results}
        return self.deduction_result

    def is_terminal(self) -> bool:
        return self.deduction_result is not None and self.deduction_result.get("all_correct", False)


def start_evidence_session(case: EvidenceCase) -> EvidenceSession:
    return EvidenceSession(case=case)


def resolve_artifact_image(artifact: Artifact) -> str | None:
    if not artifact.media or not artifact.media.image_path:
        return None
    return asset_path(artifact.media.image_path)


def format_reveal_notes(notes: RevealNotes) -> str:
    facts = "\n".join(f"- {fact}" for fact in notes.direct_archive_facts) or "- _(none listed)_"
    bridge = ""
    if notes.synthetic_bridge_allowed:
        bridge = notes.bridge_notes or "Some connective narration may be synthetic; facts below are archive-grounded."
    else:
        bridge = "This case is fully grounded in cited archive material."
    return f"**From the archive**\n{facts}\n\n**Bridge notes**\n{bridge}"
