"""Session debug logging (NDJSON). Used during ingest/Modal debugging."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_LOG = _REPO_ROOT / ".cursor" / "debug-08eda1.log"
SESSION_ID = "08eda1"


def log_path() -> Path:
    return Path(os.environ.get("ARCHIVE_DEBUG_LOG", str(_DEFAULT_LOG)))


def debug_log(
    location: str,
    message: str,
    data: dict[str, Any],
    hypothesis_id: str,
    *,
    run_id: str = "pre-fix",
) -> None:
    # #region agent log
    payload = {
        "sessionId": SESSION_ID,
        "timestamp": int(time.time() * 1000),
        "location": location,
        "message": message,
        "data": data,
        "hypothesisId": hypothesis_id,
        "runId": run_id,
    }
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str) + "\n")
    # #endregion
