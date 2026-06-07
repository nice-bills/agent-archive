from __future__ import annotations

import json
from pathlib import Path

from archive_detective.models import CaseDefinition, EvidenceCase

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "cases"


def list_cases() -> list[str]:
    if not DATA_DIR.is_dir():
        return []
    return sorted(p.stem for p in DATA_DIR.glob("*.json"))


def _read_case_json(case_id: str) -> dict:
    path = DATA_DIR / f"{case_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"No case file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def is_evidence_case_data(data: dict) -> bool:
    return data.get("mode") == "evidence_cabinet"


def load_case(case_id: str) -> CaseDefinition:
    data = _read_case_json(case_id)
    if is_evidence_case_data(data):
        raise ValueError(f"{case_id} is an evidence-cabinet case; use load_evidence_case()")
    return CaseDefinition.model_validate(data)


def load_evidence_case(case_id: str) -> EvidenceCase:
    data = _read_case_json(case_id)
    if not is_evidence_case_data(data):
        raise ValueError(f"{case_id} is a beat-based case; use load_case()")
    return EvidenceCase.model_validate(data)


def load_any_case(case_id: str) -> CaseDefinition | EvidenceCase:
    data = _read_case_json(case_id)
    if is_evidence_case_data(data):
        return EvidenceCase.model_validate(data)
    return CaseDefinition.model_validate(data)


def case_mode(case_id: str) -> str:
    data = _read_case_json(case_id)
    return "evidence_cabinet" if is_evidence_case_data(data) else "beat"


def asset_path(relative: str | None) -> str | None:
    if not relative:
        return None
    root = Path(__file__).resolve().parents[2]
    full = root / relative
    return str(full) if full.is_file() else None
