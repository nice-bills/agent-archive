from __future__ import annotations

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

CUSTOM_CSS = """
.gradio-container {
  font-family: Inter, ui-sans-serif, system-ui, sans-serif !important;
  max-width: 1180px !important;
}
#hero-title {
  font-family: Georgia, "Iowan Old Style", serif;
  font-size: 2rem;
  letter-spacing: -0.03em;
}
.mystery-pill {
  color: #fff1cc;
  border: 1px solid rgba(215,164,73,0.45);
  background: rgba(215,164,73,0.12);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  display: inline-block;
}
"""


def _mystery_badge(score: float) -> str:
    return f'<span class="mystery-pill">Mystery score {score:.0%}</span>'


def _source_md(session: CaseSession) -> str:
    src = session.pack.source
    return (
        f"**{src.publication}** · {src.date}  \n"
        f"_{src.archive}_ · [citation]({src.citation_url})"
    )


def _case_header(session: CaseSession) -> str:
    return f"## {session.case.title}\n_{session.case.tagline}_"


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
    return f"**Trail:** {steps}"


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
    )


def build_app() -> gr.Blocks:
    case_ids = list_cases() or ["georgetown_notice"]

    theme = gr.themes.Base(primary_hue="amber", neutral_hue="slate").set(
        body_background_fill="#0b0d10",
        block_background_fill="#12171e",
        border_color_primary="#2a3442",
        body_text_color="#edf2f7",
    )

    with gr.Blocks(title="Archive Detective") as demo:
        demo.theme = theme
        demo.css = CUSTOM_CSS
        session_state = gr.State(None)

        gr.Markdown(
            "# Archive Detective",
            elem_id="hero-title",
        )
        gr.Markdown(
            "Playable micro-mysteries from public-domain newspaper fragments. "
            "Read the artifact, follow the clues, pick a lead."
        )

        with gr.Row():
            case_dropdown = gr.Dropdown(
                choices=case_ids,
                value=case_ids[0],
                label="Case file",
            )
            reset_btn = gr.Button("New investigation", variant="secondary")

        case_header = gr.Markdown("")
        beat_intro = gr.Markdown("")
        mystery_html = gr.HTML("")
        source_md = gr.Markdown("")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Artifact")
                artifact_img = gr.Image(label="Clipping", type="filepath", height=320)
                raw_ocr = gr.Textbox(label="Raw OCR", lines=4, interactive=False)
                clean_text = gr.Textbox(label="Cleaned reading", lines=4, interactive=False)
            with gr.Column():
                gr.Markdown("### Evidence board")
                entities_md = gr.Markdown()
                evidence_md = gr.Markdown()
                clue_types = gr.Textbox(label="Clue types", interactive=False)
            with gr.Column():
                gr.Markdown("### Leads")
                leads_md = gr.Markdown()
                lead_radio = gr.Radio(choices=[], label="Your next move")
                advance_btn = gr.Button("Follow lead", variant="primary")
                reveal_btn = gr.Button("Reveal: archive vs bridge", variant="secondary")
                reveal_md = gr.Markdown(visible=False)

        history_md = gr.Markdown("")

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
