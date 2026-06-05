from __future__ import annotations

from dataclasses import dataclass, field

from archive_detective.cases import asset_path, load_case
from archive_detective.models import CaseDefinition, CluePack


@dataclass
class CaseSession:
    case: CaseDefinition
    beat_id: str
    history: list[tuple[str, str]] = field(default_factory=list)
    revealed: bool = False

    @property
    def pack(self) -> CluePack:
        return self.case.beats[self.beat_id]

    def choose_lead(self, lead_id: str) -> str | None:
        mapping = self.case.transitions.get(self.beat_id, {})
        next_beat = mapping.get(lead_id)
        if not next_beat:
            return None
        label = next(
            (lead.label for lead in self.pack.lead_options if lead.id == lead_id),
            lead_id,
        )
        self.history.append((self.beat_id, label))
        self.beat_id = next_beat
        self.revealed = False
        return next_beat

    def is_terminal(self) -> bool:
        return not self.case.transitions.get(self.beat_id)


def start_session(case_id: str) -> CaseSession:
    case = load_case(case_id)
    return CaseSession(case=case, beat_id=case.start_beat)


def format_entities(pack: CluePack) -> str:
    if not pack.entities:
        return "_No entities tagged yet._"
    lines = [f"- **{e.type}**: {e.value}" for e in pack.entities]
    return "\n".join(lines)


def format_evidence(pack: CluePack) -> str:
    blocks: list[str] = []
    for card in pack.evidence_cards:
        blocks.append(f"### {card.title}\n_{card.clue_type}_ — {card.detail}")
    return "\n\n".join(blocks) if blocks else "_No evidence cards._"


def format_reveal(pack: CluePack) -> str:
    notes = pack.reveal_notes
    facts = "\n".join(f"- {f}" for f in notes.direct_archive_facts) or "- _(none listed)_"
    bridge = ""
    if notes.synthetic_bridge_allowed:
        bridge = notes.bridge_notes or "Some connective narration may be synthetic; facts below are archive-grounded."
    else:
        bridge = "This beat is fully grounded in the archive fragment."
    return f"**From the archive**\n{facts}\n\n**Bridge notes**\n{bridge}"


def resolve_image(pack: CluePack) -> str | None:
    return asset_path(pack.fragment.image_path)
