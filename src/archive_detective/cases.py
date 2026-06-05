from __future__ import annotations

import json
from pathlib import Path

from archive_detective.models import CaseDefinition

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "cases"


def list_cases() -> list[str]:
    if not DATA_DIR.is_dir():
        return []
    return sorted(p.stem for p in DATA_DIR.glob("*.json"))


def load_case(case_id: str) -> CaseDefinition:
    path = DATA_DIR / f"{case_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"No case file: {path}")
    return CaseDefinition.model_validate_json(path.read_text(encoding="utf-8"))


def asset_path(relative: str | None) -> str | None:
    if not relative:
        return None
    root = Path(__file__).resolve().parents[2]
    full = root / relative
    return str(full) if full.is_file() else None
