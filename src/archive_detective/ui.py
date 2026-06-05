from __future__ import annotations

import json
from pathlib import Path

import gradio as gr

from archive_detective.cases import list_cases
from archive_detective.engine import (
    CaseSession,
    format_entities,
    format_evidence,
    format_reveal,
    resolve_image,
    start_session,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
THEME_CSS = (STATIC_DIR / "theme.css").read_text(encoding="utf-8")


def _mystery_badge(score: float) -> str:
    tier = "COLD" if score < 0.4 else "WARM" if score < 0.7 else "HOT"
    return (
        f'<span class="mystery-pill">{tier} · mystery {score:.0%}</span>'
    )


def _source_md(session: CaseSession) -> str:
    src = session.pack.source
    return (
        f'<div class="ad-board-header">'
        f"<strong>{src.publication}</strong> · {src.date}<br/>"
        f'<span style="color:#8b9aab">{src.archive}</span> · '
        f'<a href="{src.citation_url}" target="_blank" rel="noopener">citation</a>'
        f"</div>"
    )


def _case_header(session: CaseSession) -> str:
    return (
        f'<div id="hero-title">{session.case.title}</div>'
        f'<p class="ad-tagline">{session.case.tagline}</p>'
    )


def _leads_md(session: CaseSession) -> str:
    pack = session.pack
    if not pack.lead_options:
        return "_No further leads — case tabled._"
    return "\n".join(f"- **{lead.label}**" for lead in pack.lead_options)


def _lead_choices(session: CaseSession) -> list[str]:
    return [lead.label for lead in session.pack.lead_options]


def _history_md(session: CaseSession) -> str:
    if not session.history:
        return ""
    steps = " → ".join(f"{beat}: {label}" for beat, label in session.history)
    return f'<div class="trail-line"><strong>Trail</strong> {steps}</div>'


def _model_reading_md(session: CaseSession) -> str:
    pack = session.pack
    payload = {
        "artifact_id": pack.artifact_id,
        "mystery_score": pack.mystery_score,
        "clue_types": pack.clue_types,
        "entities": [e.model_dump() for e in pack.entities],
        "evidence_cards": [c.model_dump() for c in pack.evidence_cards],
        "reveal_notes": pack.reveal_notes.model_dump(),
    }
    body = json.dumps(payload, indent=2)
    return f'<pre>{body}</pre>'


def render(session: CaseSession, *, show_reveal: bool) -> tuple:
    pack = session.pack
    img = resolve_image(pack)
    labels = _lead_choices(session)
    return (
        session,
        _case_header(session),
        pack.beat_intro,
        _mystery_badge(pack.mystery_score),
        _source_md(session),
        img,
        pack.fragment.raw_ocr,
        pack.fragment.clean_text,
        format_entities(pack),
        format_evidence(pack),
        ", ".join(pack.clue_types),
        _leads_md(session),
        gr.update(choices=labels, value=labels[0] if labels else None),
        gr.update(interactive=bool(labels)),
        _history_md(session),
        gr.update(visible=show_reveal, value=format_reveal(pack) if show_reveal else ""),
        _model_reading_md(session),
    )


def build_app() -> gr.Blocks:
    case_ids = list_cases() or ["georgetown_notice"]

    theme = (
        gr.themes.Base(
            primary_hue=gr.themes.colors.amber,
            neutral_hue=gr.themes.colors.slate,
            font=gr.themes.GoogleFont("DM Sans"),
        )
        .set(
            body_background_fill="#0a0c0f",
            block_background_fill="#12171e",
            block_border_width="1px",
            block_label_text_color="#d7a449",
            body_text_color="#e8edf4",
            border_color_primary="#2a3442",
            button_primary_background_fill="linear-gradient(180deg, #c4923f, #9a6f2a)",
            button_primary_text_color="#1a1408",
            input_background_fill="#0d1117",
        )
    )

    with gr.Blocks(title="Archive Detective") as demo:
        demo.theme = theme
        demo.css = THEME_CSS
        session_state = gr.State(None)

        gr.Markdown(
            "## Archive Detective",
            elem_classes=["panel-label"],
        )
        gr.Markdown(
            "Playable micro-mysteries from **public-domain** newspaper fragments. "
            "Read the artifact · follow the evidence · pick a lead.",
            elem_classes=["ad-tagline"],
        )

        with gr.Row():
            case_dropdown = gr.Dropdown(
                choices=case_ids,
                value=case_ids[0],
                label="Case file",
                scale=2,
            )
            reset_btn = gr.Button("New investigation", variant="secondary", scale=1)

        case_header = gr.HTML("")
        beat_intro = gr.Markdown("")
        mystery_html = gr.HTML("")
        source_md = gr.HTML("")

        with gr.Tabs():
            with gr.Tab("Evidence board"):
                with gr.Row():
                    with gr.Column(scale=5):
                        gr.Markdown("### Artifact", elem_classes=["panel-label"])
                        artifact_img = gr.Image(
                            label="Clipping",
                            type="filepath",
                            height=340,
                            show_label=False,
                        )
                        with gr.Accordion("OCR layers", open=False):
                            raw_ocr = gr.Textbox(label="Raw OCR", lines=5, interactive=False)
                            clean_text = gr.Textbox(
                                label="Cleaned reading",
                                lines=5,
                                interactive=False,
                            )
                    with gr.Column(scale=4):
                        gr.Markdown("### Tagged entities", elem_classes=["panel-label"])
                        entities_md = gr.Markdown()
                        gr.Markdown("### Evidence cards", elem_classes=["panel-label"])
                        evidence_md = gr.Markdown()
                        clue_types = gr.Textbox(label="Clue types", interactive=False)
                    with gr.Column(scale=3):
                        gr.Markdown("### Leads", elem_classes=["panel-label"])
                        leads_md = gr.Markdown()
                        lead_radio = gr.Radio(choices=[], label="Your next move")
                        with gr.Row():
                            advance_btn = gr.Button("Follow lead", variant="primary")
                            reveal_btn = gr.Button("Reveal", variant="secondary")
                        reveal_md = gr.Markdown(visible=False, elem_classes=["reveal-panel"])

            with gr.Tab("Model reading"):
                gr.Markdown(
                    "Structured clue pack for this beat (cached case JSON — "
                    "live MiniCPM when `ARCHIVE_DETECTIVE_USE_MODEL=1`).",
                    elem_classes=["ad-tagline"],
                )
                model_md = gr.HTML(elem_classes=["model-tab"])

        history_md = gr.HTML("")

        outputs = [
            session_state,
            case_header,
            beat_intro,
            mystery_html,
            source_md,
            artifact_img,
            raw_ocr,
            clean_text,
            entities_md,
            evidence_md,
            clue_types,
            leads_md,
            lead_radio,
            advance_btn,
            history_md,
            reveal_md,
            model_md,
        ]

        def on_start(case_id: str):
            return render(start_session(case_id), show_reveal=False)

        def on_advance(session: CaseSession, choice: str | None):
            if session is None or not choice:
                return render(session or start_session(case_ids[0]), show_reveal=False)
            label_to_id = {lead.label: lead.id for lead in session.pack.lead_options}
            lead_id = label_to_id.get(choice)
            if lead_id:
                session.choose_lead(lead_id)
            return render(session, show_reveal=False)

        def on_reveal(session: CaseSession):
            if session is None:
                session = start_session(case_ids[0])
            session.revealed = True
            return render(session, show_reveal=True)

        reset_btn.click(on_start, [case_dropdown], outputs)
        case_dropdown.change(on_start, [case_dropdown], outputs)
        advance_btn.click(on_advance, [session_state, lead_radio], outputs)
        reveal_btn.click(on_reveal, [session_state], outputs)
        demo.load(on_start, [case_dropdown], outputs)

    return demo


def launch(**kwargs) -> None:
    app = build_app()
    app.launch(
        theme=app.theme,
        css=app.css,
        **kwargs,
    )
