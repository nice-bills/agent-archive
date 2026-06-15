/** Evidence board rendering */
import { $, escapeHtml, kindClass, kindLabel, renderMarkdownish } from "./util.js";
import * as state from "./state.js";

function applyGenerationBadge(gen, badge) {
  if (!badge) return;
  if (!gen || !gen.source) {
    badge.hidden = true;
    return;
  }
  badge.hidden = false;
  const labels = {
    cache: "Cached cabinet",
    live: "Live model",
    live_modal: "OpenBMB live",
    heuristic: "Heuristic cabinet",
    fallback: "Cached fallback",
  };
  const tips = [];
  if (gen.ocr_source === "live_vision_modal") {
    tips.push(`OCR: ${gen.ocr_model} (Modal GPU)`);
  }
  if (gen.cabinet_model) {
    tips.push(`Cabinet: ${gen.cabinet_model}`);
  }
  if (gen.skeleton_filled?.length) {
    tips.push(`Archivist bridge filled: ${gen.skeleton_filled.join(", ")}`);
  }
  badge.title = tips.join(" · ");
  badge.textContent = labels[gen.source] || gen.source;
  badge.className = `generation-badge source-${gen.source}`;
  if (gen.live_error) {
    badge.title = [badge.title, gen.live_error].filter(Boolean).join(" · ");
  }
}

function updateRegenerateButton(gen) {
  const btn = $("btn-regenerate");
  if (!btn) return;
  const show = Boolean(gen?.clipping_id) && gen?.source !== "heuristic";
  btn.hidden = !show;
}

export function renderDeductionField(field, answers) {
  const fieldset = document.createElement("fieldset");
  fieldset.className = "deduction-field";
  const legend = document.createElement("legend");
  legend.className = "field-label";
  legend.textContent = field.label;
  fieldset.appendChild(legend);

  const pills = document.createElement("div");
  pills.className = "option-pills";
  pills.setAttribute("role", "radiogroup");
  pills.setAttribute("aria-label", field.label);

  for (const opt of field.options || []) {
    const label = document.createElement("label");
    label.className = "option-pill";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = field.id;
    input.value = opt;
    input.required = true;
    if (answers?.[field.id] === opt) input.checked = true;
    const span = document.createElement("span");
    span.textContent = opt;
    label.append(input, span);
    pills.appendChild(label);
  }
  fieldset.appendChild(pills);
  return fieldset;
}

export function updateGenerationBadge(gen) {
  applyGenerationBadge(gen, $("generation-badge"));
  applyGenerationBadge(gen, $("board-generation-badge"));
  updateRegenerateButton(gen);
}

export function showReveal(text, panelId = "reveal-panel") {
  const panel = $(panelId);
  if (!panel) return;
  panel.hidden = false;
  panel.classList.add("visible");
  panel.innerHTML = `<div class="reveal-inner">${renderMarkdownish(text)}</div>`;
}

export function renderEvidenceCabinet(sess, { animate = true, onLead, onSelectArtifact } = {}) {
  $("cabinet-layout").hidden = false;
  $("beat-layout").hidden = true;
  $("search-console").hidden = false;

  const unlocked = sess.unlocked_artifacts?.length || 0;
  const total = sess.artifacts?.length || 0;
  $("status-badge").textContent = `${unlocked}/${total} artifacts unlocked`;
  $("status-badge").className = "status-stamp warm";
  const gen = sess.generation || {};
  const ocrTag =
    gen.ocr_source && gen.ocr_source.startsWith("live")
      ? ` · OCR ${escapeHtml(gen.ocr_model || "model")}`
      : "";
  const genTag = gen.source
    ? ` · ${escapeHtml(String(gen.source).toUpperCase())}${gen.model_id ? ` (${escapeHtml(gen.model_id)})` : ""}${ocrTag}`
    : ocrTag;
  $("case-intro").textContent =
    (sess.followed_leads?.length > 0
      ? `Trail · ${sess.followed_leads.length} lead(s) followed. Keep pulling threads.`
      : "Something in the ink doesn't add up. Open a piece from the tray, then chase a lead.") + genTag;
  updateGenerationBadge(gen);

  $("tray-count").textContent = `${unlocked} of ${total} open`;

  const tray = $("artifact-tray");
  tray.innerHTML = "";
  for (const art of sess.artifacts || []) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "artifact-card";
    card.dataset.artifactId = art.artifact_id;
    if (!art.unlocked) card.classList.add("locked");
    if (art.selected) card.classList.add("selected");
    if (art.search_hit) card.classList.add("search-hit");
    card.setAttribute("role", "listitem");
    card.setAttribute("aria-label", `${art.title}${art.unlocked ? "" : " (locked)"}`);

    const thumb = art.thumb_url
      ? `<img src="${escapeHtml(art.thumb_url)}" alt="" class="artifact-thumb" />`
      : `<span class="artifact-thumb placeholder">${escapeHtml(kindLabel(art.kind).slice(0, 1))}</span>`;

    card.innerHTML = `
      ${thumb}
      <span class="artifact-card-kind ${kindClass(art.kind)}">${escapeHtml(kindLabel(art.kind))}</span>
      <span class="artifact-card-title">${escapeHtml(art.title)}</span>
      ${art.unlocked ? "" : '<span class="wax-seal" aria-hidden="true">SEALED</span><span class="lock-tag">Wax sealed</span>'}
    `;
    card.disabled = !art.unlocked;
    card.addEventListener("click", () => onSelectArtifact(art.artifact_id));
    if (animate) card.classList.add("enter");
    tray.appendChild(card);
  }

  const selected = sess.selected_artifact || {};
  $("viewer-label").textContent = selected.title || "Artifact";
  const kindEl = $("viewer-kind");
  kindEl.textContent = kindLabel(selected.kind || "");
  kindEl.className = `kind-stamp ${kindClass(selected.kind || "")}`;

  const img = $("artifact-img");
  const frame = $("artifact-frame");
  if (selected.image_url) {
    img.src = selected.image_url;
    img.alt = selected.title || "Archive artifact";
    img.hidden = false;
    frame.classList.remove("no-image");
  } else {
    img.removeAttribute("src");
    img.hidden = true;
    frame.classList.add("no-image");
  }
  $("artifact-caption").textContent = selected.title || "";

  const textBlock = $("artifact-text");
  if (selected.clean_text) {
    textBlock.hidden = false;
    textBlock.textContent = selected.clean_text;
  } else {
    textBlock.hidden = true;
    textBlock.textContent = "";
  }

  const src = selected.source || {};
  const strip = $("citation-strip");
  const hasCitation = src.publication || src.date || src.archive;
  if (hasCitation) {
    strip.hidden = false;
    const parts = [src.publication, src.date].filter(Boolean).join(" · ");
    $("citation-line").textContent = src.archive ? `${parts} — ${src.archive}` : parts || src.archive;
    const link = $("citation-link");
    if (src.citation_url) {
      link.href = src.citation_url;
      link.hidden = false;
    } else {
      link.hidden = true;
    }
  } else {
    strip.hidden = true;
  }

  $("citation-body").innerHTML = `
    <p><strong>${escapeHtml(src.publication || "—")}</strong> · ${escapeHtml(src.date || "—")}</p>
    <p>${escapeHtml(src.archive || "")}</p>
    ${src.citation_url ? `<a href="${escapeHtml(src.citation_url)}" target="_blank" rel="noopener">View citation</a>` : ""}
  `;

  $("raw-ocr").textContent = selected.raw_ocr || "(none)";
  $("clean-text").textContent = selected.clean_text || "(none)";

  const pinned = $("pinned-cards");
  pinned.innerHTML = "";
  const cards = sess.evidence_cards || [];
  if (!cards.length) {
    pinned.innerHTML = '<p class="empty-state">Pin clues by unlocking artifacts.</p>';
  } else {
    for (const card of cards) {
      const el = document.createElement("article");
      el.className = "evidence-card";
      if (animate) el.classList.add("enter");
      el.innerHTML = `<div class="type">${escapeHtml(card.clue_type)}</div><h3>${escapeHtml(card.title)}</h3><p>${escapeHtml(card.detail)}</p>`;
      pinned.appendChild(el);
    }
  }

  const leads = $("lead-buttons");
  leads.innerHTML = "";
  const leadList = sess.leads || [];
  if (!leadList.length) {
    leads.innerHTML = '<p class="empty-state">All leads followed — complete the deduction sheet.</p>';
  } else {
    for (const lead of leadList) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn lead";
      btn.textContent = lead.label;
      btn.disabled = false;
      btn.addEventListener("click", () => {
        btn.classList.add("lead-hit");
        onLead(lead.id);
      });
      leads.appendChild(btn);
    }
  }

  const sheet = sess.deduction_sheet || {};
  $("deduction-prompt").textContent = sheet.prompt || "";

  const form = $("deduction-form");
  form.innerHTML = "";
  for (const field of sheet.fields || []) {
    form.appendChild(renderDeductionField(field, sheet.answers));
  }

  const resultEl = $("deduction-result");
  if (sheet.result) {
    resultEl.hidden = false;
    resultEl.classList.toggle("stamp-accepted", sheet.result.all_correct);
    resultEl.classList.toggle("shake-wrong", !sheet.result.all_correct);
    const lines = sheet.result.fields
      .map((f) => `${f.correct ? "✓" : "✗"} ${escapeHtml(f.label)}`)
      .join("<br/>");
    resultEl.innerHTML = `<p><strong>${sheet.result.all_correct ? "Deduction accepted." : "Some fields need revision."}</strong></p>${lines}`;
  } else {
    resultEl.hidden = true;
    resultEl.innerHTML = "";
  }

  const search = sess.search || {};
  $("search-status").textContent = search.query
    ? `${search.count || 0} match(es) for “${search.query}”`
    : "Search unlocked artifact text";

  if (sess.reveal) {
    showReveal(sess.reveal, "reveal-panel");
  } else {
    const panel = $("reveal-panel");
    if (panel) {
      panel.hidden = true;
      panel.classList.remove("visible");
    }
  }
}

export function renderBeatCase(sess, { animate = true, onLead } = {}) {
  $("cabinet-layout").hidden = true;
  $("beat-layout").hidden = false;
  $("search-console").hidden = true;

  const pack = sess.pack;
  $("status-badge").textContent = `${pack.mystery_tier} · mystery ${Math.round(pack.mystery_score * 100)}%`;
  $("status-badge").className = `status-stamp ${pack.mystery_tier}`;
  $("case-intro").textContent = pack.beat_intro;

  const src = pack.source;
  $("source-line").textContent = `${src.publication} · ${src.date}`;

  const img = $("clipping-img");
  const frame = $("clipping-frame");
  if (pack.image_url) {
    img.src = pack.image_url;
    img.hidden = false;
    frame.classList.remove("no-image");
  } else {
    img.removeAttribute("src");
    img.hidden = true;
    frame.classList.add("no-image");
  }

  $("beat-raw-ocr").textContent = pack.raw_ocr || "(none)";
  $("beat-clean-text").textContent = pack.clean_text || "(none)";
  $("clue-types").textContent = pack.clue_types?.join(", ") || "—";

  const stack = $("evidence-stack");
  stack.innerHTML = "";
  if (!pack.evidence_cards?.length) {
    stack.innerHTML = '<p class="empty-state">No cards pinned yet — read the clipping and pick a lead.</p>';
  } else {
    for (const card of pack.evidence_cards) {
      const el = document.createElement("article");
      el.className = "evidence-card";
      if (animate) el.classList.add("enter");
      el.innerHTML = `<div class="type">${escapeHtml(card.clue_type)}</div><h3>${escapeHtml(card.title)}</h3><p>${escapeHtml(card.detail)}</p>`;
      stack.appendChild(el);
    }
  }

  const rail = $("entity-rail");
  rail.innerHTML = "";
  if (!pack.entities?.length) {
    rail.innerHTML = '<span class="hint">No named entities extracted for this beat.</span>';
  } else {
    for (const ent of pack.entities) {
      const tag = document.createElement("span");
      tag.className = "entity-tag";
      tag.innerHTML = `<em>${escapeHtml(ent.type)}</em>${escapeHtml(ent.value)}`;
      rail.appendChild(tag);
    }
  }

  const leads = $("beat-lead-buttons");
  leads.innerHTML = "";
  if (!pack.leads?.length) {
    leads.innerHTML =
      '<p class="empty-state">This beat is terminal — reveal archive facts or start a new investigation.</p>';
  } else {
    for (const lead of pack.leads) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn lead";
      btn.textContent = lead.label;
      btn.disabled = false;
      btn.addEventListener("click", () => {
        btn.classList.add("lead-hit");
        onLead(lead.id);
      });
      leads.appendChild(btn);
    }
  }

  const trail = sess.history?.length
    ? sess.history.map((h) => `${h.beat}: ${h.label}`).join(" → ")
    : "";
  $("trail").textContent = trail ? `Trail · ${trail}` : "Trail · opening beat";

  const reveal = $("beat-reveal-panel");
  if (pack.reveal) {
    reveal.hidden = false;
    reveal.classList.add("visible");
    reveal.innerHTML = `<div class="reveal-inner">${renderMarkdownish(pack.reveal)}</div>`;
  } else {
    reveal.hidden = true;
    reveal.classList.remove("visible");
    reveal.innerHTML = "";
  }
}
