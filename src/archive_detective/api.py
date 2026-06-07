"""JSON API payloads for the custom gr.Server frontend."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from archive_detective.cases import case_mode, list_cases as _list_cases, load_any_case
from archive_detective.engine import (
    CaseSession,
    format_evidence,
    format_reveal,
    resolve_image,
    start_session,
)
from archive_detective.evidence_engine import (
    EvidenceSession,
    format_reveal_notes,
    resolve_artifact_image,
    start_evidence_session,
)
from archive_detective.models import Artifact, CluePack, EvidenceCase


# Hero demos first in the case picker.
_HERO_ORDER = (
    "hart_notice_evidence_cabinet",
    "georgetown_notice",
    "case_1937_04_22_resource_sn83045462_1",
)


def _case_meta(case_id: str) -> dict[str, str]:
    loaded = load_any_case(case_id)
    mode = case_mode(case_id)
    return {
        "id": case_id,
        "title": loaded.title,
        "tagline": loaded.tagline,
        "mode": mode,
        "hero": case_id in _HERO_ORDER,
    }


def list_case_catalog() -> list[dict[str, str]]:
    case_ids = _list_cases()
    ordered = sorted(
        case_ids,
        key=lambda cid: (
            _HERO_ORDER.index(cid) if cid in _HERO_ORDER else len(_HERO_ORDER),
            cid,
        ),
    )
    return [_case_meta(case_id) for case_id in ordered]


def _image_url(pack: CluePack) -> str | None:
    path = resolve_image(pack)
    if not path:
        return None
    rel = pack.fragment.image_path
    if rel and rel.startswith("assets/"):
        return f"/{rel}"
    return None


def _artifact_image_url(artifact: Artifact) -> str | None:
    path = resolve_artifact_image(artifact)
    if not path:
        return None
    if artifact.media and artifact.media.image_path and artifact.media.image_path.startswith("assets/"):
        return f"/{artifact.media.image_path}"
    return None


def _artifact_thumb_url(artifact: Artifact) -> str | None:
    if artifact.media and artifact.media.thumb_path and artifact.media.thumb_path.startswith("assets/"):
        return f"/{artifact.media.thumb_path}"
    return _artifact_image_url(artifact)


def pack_to_dict(pack: CluePack, *, show_reveal: bool) -> dict:
    return {
        "artifact_id": pack.artifact_id,
        "beat_intro": pack.beat_intro,
        "mystery_score": pack.mystery_score,
        "mystery_tier": (
            "cold" if pack.mystery_score < 0.4 else "warm" if pack.mystery_score < 0.7 else "hot"
        ),
        "source": {
            "publication": pack.source.publication,
            "date": pack.source.date,
            "archive": pack.source.archive,
            "citation_url": pack.source.citation_url,
        },
        "image_url": _image_url(pack),
        "raw_ocr": pack.fragment.raw_ocr,
        "clean_text": pack.fragment.clean_text,
        "entities": [e.model_dump() for e in pack.entities],
        "evidence_cards": [c.model_dump() for c in pack.evidence_cards],
        "clue_types": pack.clue_types,
        "evidence_md": format_evidence(pack),
        "leads": [{"id": l.id, "label": l.label} for l in pack.lead_options],
        "reveal": format_reveal(pack) if show_reveal else None,
        "model_reading": {
            "artifact_id": pack.artifact_id,
            "mystery_score": pack.mystery_score,
            "clue_types": pack.clue_types,
            "entities": [e.model_dump() for e in pack.entities],
            "evidence_cards": [c.model_dump() for c in pack.evidence_cards],
            "reveal_notes": pack.reveal_notes.model_dump(),
        },
    }


def session_to_dict(session: CaseSession, *, show_reveal: bool) -> dict:
    return {
        "mode": "beat",
        "case_id": session.case.case_id,
        "title": session.case.title,
        "tagline": session.case.tagline,
        "beat_id": session.beat_id,
        "terminal": session.is_terminal(),
        "history": [{"beat": b, "label": label} for b, label in session.history],
        "pack": pack_to_dict(session.pack, show_reveal=show_reveal),
    }


def _artifact_to_dict(artifact: Artifact, session: EvidenceSession) -> dict:
    unlocked = artifact.artifact_id in session.unlocked
    selected = artifact.artifact_id == session.selected_artifact_id
    search_hit = artifact.artifact_id in session.search_matches
    text = artifact.text or None
    return {
        "artifact_id": artifact.artifact_id,
        "kind": artifact.kind,
        "title": artifact.title,
        "unlocked": unlocked,
        "selected": selected,
        "search_hit": search_hit,
        "source": {
            "publication": artifact.source.publication,
            "date": artifact.source.date,
            "archive": artifact.source.archive,
            "citation_url": artifact.source.citation_url,
        },
        "image_url": _artifact_image_url(artifact) if unlocked else None,
        "thumb_url": _artifact_thumb_url(artifact) if unlocked else None,
        "raw_ocr": text.raw_ocr if text and unlocked else "",
        "clean_text": text.clean_text if text and unlocked else "",
        "entities": [e.model_dump() for e in artifact.entities] if unlocked else [],
        "evidence_cards": [c.model_dump() for c in artifact.evidence_cards] if unlocked else [],
    }


def evidence_case_to_dict(
    session: EvidenceSession,
    *,
    show_reveal: bool,
    generation: dict | None = None,
) -> dict:
    case = session.case
    selected = session.selected_artifact
    visible_cards: list[dict] = []
    for art in case.artifacts:
        if art.artifact_id not in session.unlocked:
            continue
        for card in art.evidence_cards:
            visible_cards.append({**card.model_dump(), "artifact_id": art.artifact_id})

    remaining_leads = [
        {"id": lead.id, "label": lead.label, "unlocks": lead.unlocks}
        for lead in case.leads
        if lead.id not in session.followed_leads
    ]

    return {
        "mode": "evidence_cabinet",
        "case_id": case.case_id,
        "title": case.title,
        "tagline": case.tagline,
        "hero_artifact_id": case.hero_artifact_id,
        "selected_artifact_id": session.selected_artifact_id,
        "unlocked_artifacts": sorted(session.unlocked),
        "artifacts": [_artifact_to_dict(art, session) for art in case.artifacts],
        "selected_artifact": _artifact_to_dict(selected, session),
        "evidence_cards": visible_cards,
        "pinned_cards": sorted(session.pinned_cards),
        "leads": remaining_leads,
        "followed_leads": list(session.followed_leads),
        "search": {
            "query": session.search_query,
            "matches": list(session.search_matches),
            "count": len(session.search_matches),
        },
        "deduction_sheet": {
            "prompt": case.deduction_sheet.prompt,
            "fields": [f.model_dump() for f in case.deduction_sheet.fields],
            "answers": session.deduction_answers,
            "result": session.deduction_result,
        },
        "terminal": session.is_terminal(),
        "reveal": format_reveal_notes(case.reveal_notes) if show_reveal else None,
        "generation": generation,
    }


def any_session_to_dict(
    session: GameSession,
    *,
    show_reveal: bool,
    generation: dict | None = None,
) -> dict:
    if session.mode == "evidence_cabinet":
        assert session.evidence is not None
        return evidence_case_to_dict(
            session.evidence,
            show_reveal=show_reveal,
            generation=generation or session.generation,
        )
    assert session.beat is not None
    return session_to_dict(session.beat, show_reveal=show_reveal)


@dataclass
class GameSession:
    mode: str
    beat: CaseSession | None = None
    evidence: EvidenceSession | None = None
    generation: dict | None = None

    @property
    def case_id(self) -> str:
        if self.evidence:
            return self.evidence.case.case_id
        if self.beat:
            return self.beat.case.case_id
        return ""


def start_game_session(case_id: str) -> GameSession:
    loaded = load_any_case(case_id)
    if isinstance(loaded, EvidenceCase):
        return GameSession(mode="evidence_cabinet", evidence=start_evidence_session(loaded))
    return GameSession(mode="beat", beat=start_session(case_id))


def start_generated_session(case: EvidenceCase, *, generation: dict | None = None) -> GameSession:
    return GameSession(
        mode="evidence_cabinet",
        evidence=start_evidence_session(case),
        generation=generation,
    )


@dataclass
class SessionStore:
    """In-memory sessions for the Server API."""

    _sessions: dict[str, GameSession] = field(default_factory=dict)

    def create(self, case_id: str) -> tuple[str, GameSession]:
        import secrets

        sid = secrets.token_hex(12)
        session = start_game_session(case_id)
        self._sessions[sid] = session
        return sid, session

    def create_from_evidence_case(
        self,
        case: EvidenceCase,
        *,
        generation: dict | None = None,
    ) -> tuple[str, GameSession]:
        import secrets

        sid = secrets.token_hex(12)
        session = start_generated_session(case, generation=generation)
        self._sessions[sid] = session
        return sid, session

    def get(self, session_id: str) -> GameSession | None:
        return self._sessions.get(session_id)

    def reset(self, session_id: str, case_id: str) -> GameSession | None:
        if session_id not in self._sessions:
            return None
        session = start_game_session(case_id)
        self._sessions[session_id] = session
        return session

    def require(self, session_id: str) -> GameSession:
        session = self.get(session_id)
        if session is None:
            raise ValueError("Session expired — reload the case.")
        return session

    def require_evidence(self, session_id: str) -> EvidenceSession:
        game = self.require(session_id)
        if game.mode != "evidence_cabinet" or game.evidence is None:
            raise ValueError("This action requires an evidence-cabinet case.")
        return game.evidence

    def require_beat(self, session_id: str) -> CaseSession:
        game = self.require(session_id)
        if game.mode != "beat" or game.beat is None:
            raise ValueError("This action requires a beat-based case.")
        return game.beat
