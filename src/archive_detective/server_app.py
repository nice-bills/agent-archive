"""Custom frontend via gradio.Server (Off-Brand badge path)."""

from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from gradio import Server

from archive_detective.static_files import NoCacheStaticFiles

from archive_detective.api import SessionStore, any_session_to_dict, list_case_catalog
from archive_detective.generation import (
    UPLOAD_NO_OCR_SPACE_MSG,
    gallery_catalog,
    generate_from_gallery,
    generate_from_upload,
)
from archive_detective.hf_inference import DEFAULT_MODEL, hf_enabled
from archive_detective.modal_play import cabinet_model_label, vision_model_label
from archive_detective.play_pipeline import play_backend_name
from archive_detective.ocr_inference import vision_enabled

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static" / "board"
ASSETS = ROOT / "assets"

store = SessionStore()


def _generation_api_error(exc: BaseException) -> dict:
    """Structured failure the board can show instead of an empty Gradio response."""
    msg = str(exc).strip() or type(exc).__name__
    code = "generation_failed"
    lower = msg.lower()
    if isinstance(exc, ValueError) and "paste ocr" in lower:
        code = "paste_ocr_required"
    elif isinstance(exc, TimeoutError) or "timeout" in lower or "timed out" in lower:
        code = "modal_timeout"
    elif isinstance(exc, RuntimeError) and (
        "modal" in lower or "hf_token" in lower or "model generation" in lower
    ):
        code = "backend_unavailable"
    elif isinstance(exc, FileNotFoundError):
        code = "missing_asset"
    return {"ok": False, "error": msg, "error_code": code}


def build_server() -> Server:
    app = Server(title="Archive Detective")

    @app.get("/")
    async def home():
        return FileResponse(
            STATIC / "index.html",
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )

    app.mount(
        "/board",
        NoCacheStaticFiles(directory=str(STATIC)),
        name="board_static",
    )

    if ASSETS.is_dir():
        app.mount("/assets", StaticFiles(directory=str(ASSETS)), name="assets")

    @app.api(name="model_info")
    def model_info() -> dict:
        import os

        on_space = bool(os.environ.get("SPACE_ID"))
        if play_backend_name() == "modal_openbmb":
            ocr_model = vision_model_label()
            cabinet_model = cabinet_model_label()
            return {
                "text_model": cabinet_model,
                "cabinet_model": cabinet_model,
                "cabinet_mode": "modal",
                "ocr_model": ocr_model,
                "ocr_mode": "modal",
                "stack": "openbmb",
                "hf_enabled": hf_enabled(),
                "modal_enabled": True,
                "live_required": True,
                "on_space": on_space,
                "upload_requires_ocr": on_space,
                "upload_hint": UPLOAD_NO_OCR_SPACE_MSG,
            }
        ocr_mode = "vision" if vision_enabled() else "hosted_refine"
        ocr_model = (
            vision_model_label()
            if vision_enabled()
            else os.environ.get("ARCHIVE_DETECTIVE_HF_OCR_MODEL", DEFAULT_MODEL)
        )
        cabinet_model = os.environ.get("ARCHIVE_DETECTIVE_HF_MODEL", DEFAULT_MODEL)
        return {
            "text_model": cabinet_model,
            "cabinet_model": cabinet_model,
            "cabinet_mode": "hosted",
            "ocr_model": ocr_model,
            "ocr_mode": ocr_mode,
            "stack": "mixed",
            "hf_enabled": hf_enabled(),
            "modal_enabled": False,
            "live_required": True,
            "on_space": on_space,
            "upload_requires_ocr": False,
            "upload_hint": None,
        }

    @app.api(name="catalog")
    def catalog() -> list[dict]:
        return list_case_catalog()

    @app.api(name="gallery_catalog")
    def gallery_catalog_api() -> list[dict]:
        return gallery_catalog()

    @app.api(name="generate_from_gallery", concurrency_limit=1)
    def generate_from_gallery_api(clipping_id: str, regenerate: bool = False) -> dict:
        try:
            case, meta = generate_from_gallery(clipping_id, regenerate=regenerate)
            sid, session = store.create_from_evidence_case(case, generation=meta)
            return {
                "ok": True,
                "session_id": sid,
                **any_session_to_dict(session, show_reveal=False),
            }
        except Exception as exc:
            return _generation_api_error(exc)

    @app.api(name="generate_from_upload", concurrency_limit=1)
    def generate_from_upload_api(
        image_b64: str,
        title: str = "Uploaded clipping",
        raw_ocr: str = "",
        regenerate: bool = False,
    ) -> dict:
        try:
            case, meta = generate_from_upload(
                image_b64,
                title=title,
                raw_ocr=raw_ocr,
                regenerate=regenerate,
            )
            sid, session = store.create_from_evidence_case(case, generation=meta)
            return {
                "ok": True,
                "session_id": sid,
                **any_session_to_dict(session, show_reveal=False),
            }
        except Exception as exc:
            return _generation_api_error(exc)

    @app.api(name="start_case")
    def start_case(case_id: str) -> dict:
        sid, session = store.create(case_id)
        return {"session_id": sid, **any_session_to_dict(session, show_reveal=False)}

    @app.api(name="reset_case")
    def reset_case(session_id: str, case_id: str) -> dict:
        session = store.reset(session_id, case_id)
        if session is None:
            sid, session = store.create(case_id)
            return {"session_id": sid, **any_session_to_dict(session, show_reveal=False)}
        return {"session_id": session_id, **any_session_to_dict(session, show_reveal=False)}

    @app.api(name="choose_lead")
    def choose_lead(session_id: str, lead_id: str) -> dict:
        game = store.require(session_id)
        if game.mode == "evidence_cabinet":
            assert game.evidence is not None
            if not game.evidence.choose_lead(lead_id):
                raise ValueError(f"Unknown lead: {lead_id}")
        else:
            assert game.beat is not None
            game.beat.choose_lead(lead_id)
        return {"session_id": session_id, **any_session_to_dict(game, show_reveal=False)}

    @app.api(name="select_artifact")
    def select_artifact(session_id: str, artifact_id: str) -> dict:
        evidence = store.require_evidence(session_id)
        if not evidence.select_artifact(artifact_id):
            raise ValueError(f"Artifact locked or unknown: {artifact_id}")
        game = store.require(session_id)
        return {"session_id": session_id, **any_session_to_dict(game, show_reveal=False)}

    @app.api(name="search_case")
    def search_case(session_id: str, query: str) -> dict:
        evidence = store.require_evidence(session_id)
        evidence.search(query)
        game = store.require(session_id)
        return {"session_id": session_id, **any_session_to_dict(game, show_reveal=False)}

    @app.api(name="submit_deduction")
    def submit_deduction(session_id: str, answers: dict) -> dict:
        evidence = store.require_evidence(session_id)
        evidence.submit_deduction(answers)
        game = store.require(session_id)
        return {"session_id": session_id, **any_session_to_dict(game, show_reveal=False)}

    @app.api(name="reveal")
    def reveal(session_id: str) -> dict:
        game = store.require(session_id)
        if game.mode == "evidence_cabinet":
            assert game.evidence is not None
            game.evidence.revealed = True
        else:
            assert game.beat is not None
            game.beat.revealed = True
        return {"session_id": session_id, **any_session_to_dict(game, show_reveal=True)}

    return app


def launch(**kwargs) -> None:
    defaults = {
        "server_name": "127.0.0.1",
        "server_port": 7860,
        "show_error": True,
        "footer_links": None,
        "css": (
            "footer { display: none !important; } "
            ".gradio-container { padding: 0 !important; max-width: none !important; width: 100% !important; }"
        ),
    }
    defaults.update(kwargs)
    url = f"http://{defaults['server_name']}:{defaults['server_port']}/"
    print(f"\nArchive Detective (custom board) → {url}\n")
    build_server().launch(**defaults)
