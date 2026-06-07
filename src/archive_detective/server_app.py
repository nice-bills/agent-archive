"""Custom frontend via gradio.Server (Off-Brand badge path)."""

from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from gradio import Server

from archive_detective.api import SessionStore, any_session_to_dict, list_case_catalog
from archive_detective.generation import (
    gallery_catalog,
    generate_from_gallery,
    generate_from_upload,
)

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static" / "board"
ASSETS = ROOT / "assets"

store = SessionStore()


def build_server() -> Server:
    app = Server(title="Archive Detective")

    @app.get("/")
    async def home():
        return FileResponse(STATIC / "index.html")

    @app.get("/board.css")
    async def board_css():
        return FileResponse(
            STATIC / "board.css",
            media_type="text/css",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/board.js")
    async def board_js():
        return FileResponse(
            STATIC / "board.js",
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )

    if ASSETS.is_dir():
        app.mount("/assets", StaticFiles(directory=str(ASSETS)), name="assets")

    @app.api(name="catalog")
    def catalog() -> list[dict]:
        return list_case_catalog()

    @app.api(name="gallery_catalog")
    def gallery_catalog_api() -> list[dict]:
        return gallery_catalog()

    @app.api(name="generate_from_gallery")
    def generate_from_gallery_api(clipping_id: str, regenerate: bool = False) -> dict:
        case, meta = generate_from_gallery(clipping_id, regenerate=regenerate)
        sid, session = store.create_from_evidence_case(case, generation=meta)
        return {"session_id": sid, **any_session_to_dict(session, show_reveal=False)}

    @app.api(name="generate_from_upload")
    def generate_from_upload_api(
        image_b64: str,
        title: str = "Uploaded clipping",
        raw_ocr: str = "",
        regenerate: bool = False,
    ) -> dict:
        case, meta = generate_from_upload(
            image_b64,
            title=title,
            raw_ocr=raw_ocr,
            regenerate=regenerate,
        )
        sid, session = store.create_from_evidence_case(case, generation=meta)
        return {"session_id": sid, **any_session_to_dict(session, show_reveal=False)}

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
    }
    defaults.update(kwargs)
    url = f"http://{defaults['server_name']}:{defaults['server_port']}/"
    print(f"\nArchive Detective (custom board) → {url}\n")
    build_server().launch(**defaults)
