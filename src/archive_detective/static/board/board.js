/** Archive Detective — Evidence Cabinet board (gradio.Server APIs) */

async function callApi(name, ...args) {
  const res = await fetch(`/gradio_api/call/${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data: args }),
  });
  if (!res.ok) {
    throw new Error(`API ${name} failed (${res.status})`);
  }
  const envelope = await res.json();
  const eventId = envelope.event_id;
  if (!eventId) {
    throw new Error(`No event_id from ${name}`);
  }
  const poll = await fetch(`/gradio_api/call/${name}/${eventId}`);
  if (!poll.ok) {
    throw new Error(`Poll ${name} failed (${poll.status})`);
  }
  const raw = await poll.text();
  for (const line of raw.split("\n")) {
    if (!line.startsWith("data: ")) continue;
    const payload = JSON.parse(line.slice(6));
    if (Array.isArray(payload) && payload.length) {
      return payload[0];
    }
    return payload;
  }
  throw new Error(`${name} returned no data`);
}

const $ = (id) => document.getElementById(id);

const KIND_LABELS = {
  newspaper: "Notice",
  map: "Map",
  letter: "Letter",
  photo: "Photo",
  object: "Object",
  directory: "Directory",
  trial: "Trial",
  notice: "Notice",
  clipping: "Clipping",
};

let sessionId = null;
let catalog = [];
let busy = false;
let currentState = null;

function showError(msg) {
  const el = $("error");
  el.hidden = false;
  el.textContent = msg;
}

function clearError() {
  $("error").hidden = true;
}

function setBusy(on, label = "Working…") {
  busy = on;
  const loading = $("loading");
  loading.hidden = !on;
  if (on) {
    loading.textContent = label;
    loading.dataset.mode = label.includes("case") ? "full" : "inline";
  }
}

function renderMarkdownish(text) {
  if (!text) return "";
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br/>");
}

function kindLabel(kind) {
  return KIND_LABELS[kind] || kind;
}

function kindClass(kind) {
  const map = {
    newspaper: "kind-notice",
    notice: "kind-notice",
    clipping: "kind-notice",
    trial: "kind-notice",
    map: "kind-map",
    letter: "kind-letter",
    photo: "kind-photo",
    directory: "kind-directory",
    object: "kind-object",
  };
  return map[kind] || "kind-object";
}

function renderState(state, { animate = true } = {}) {
  clearError();
  currentState = state;
  $("board").hidden = false;
  setBusy(false);

  $("case-title").textContent = state.title;
  $("case-tagline").textContent = state.tagline;

  if (state.mode === "evidence_cabinet") {
    renderEvidenceCabinet(state, { animate });
  } else {
    renderBeatCase(state, { animate });
  }

  $("model-reading").textContent = JSON.stringify(state, null, 2);

  if (animate) {
    $("board").classList.remove("enter");
    void $("board").offsetWidth;
    $("board").classList.add("enter");
  }
}

function renderEvidenceCabinet(state, { animate = true }) {
  $("cabinet-layout").hidden = false;
  $("beat-layout").hidden = true;
  $("search-console").hidden = false;

  const unlocked = state.unlocked_artifacts?.length || 0;
  const total = state.artifacts?.length || 0;
  $("status-badge").textContent = `${unlocked}/${total} artifacts unlocked`;
  $("status-badge").className = "status-stamp warm";
  const gen = state.generation || {};
  const genTag = gen.source
    ? ` · ${String(gen.source).toUpperCase()}${gen.model_id ? ` (${gen.model_id})` : ""}`
    : "";
  $("case-intro").textContent =
    (state.followed_leads?.length > 0
      ? `Trail · ${state.followed_leads.length} lead(s) followed`
      : "Open an artifact from the tray. Follow leads to unlock more evidence.") + genTag;
  updateGenerationBadge(gen);

  $("tray-count").textContent = `${unlocked} of ${total} open`;

  const tray = $("artifact-tray");
  tray.innerHTML = "";
  for (const art of state.artifacts || []) {
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
      ? `<img src="${art.thumb_url}" alt="" class="artifact-thumb" />`
      : `<span class="artifact-thumb placeholder">${kindLabel(art.kind).slice(0, 1)}</span>`;

    card.innerHTML = `
      ${thumb}
      <span class="artifact-card-kind ${kindClass(art.kind)}">${kindLabel(art.kind)}</span>
      <span class="artifact-card-title">${art.title}</span>
      ${art.unlocked ? "" : '<span class="lock-tag">Wax sealed</span>'}
    `;
    card.disabled = !art.unlocked || busy;
    card.addEventListener("click", () => onSelectArtifact(art.artifact_id));
    if (animate) card.classList.add("enter");
    tray.appendChild(card);
  }

  const selected = state.selected_artifact || {};
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
    <p><strong>${src.publication || "—"}</strong> · ${src.date || "—"}</p>
    <p>${src.archive || ""}</p>
    ${src.citation_url ? `<a href="${src.citation_url}" target="_blank" rel="noopener">View citation</a>` : ""}
  `;

  $("raw-ocr").textContent = selected.raw_ocr || "(none)";
  $("clean-text").textContent = selected.clean_text || "(none)";

  const pinned = $("pinned-cards");
  pinned.innerHTML = "";
  const cards = state.evidence_cards || [];
  if (!cards.length) {
    pinned.innerHTML = '<p class="empty-state">Pin clues by unlocking artifacts.</p>';
  } else {
    for (const card of cards) {
      const el = document.createElement("article");
      el.className = "evidence-card";
      if (animate) el.classList.add("enter");
      el.innerHTML = `<div class="type">${card.clue_type}</div><h3>${card.title}</h3><p>${card.detail}</p>`;
      pinned.appendChild(el);
    }
  }

  const leads = $("lead-buttons");
  leads.innerHTML = "";
  const leadList = state.leads || [];
  if (!leadList.length) {
    leads.innerHTML = '<p class="empty-state">All leads followed — complete the deduction sheet.</p>';
  } else {
    for (const lead of leadList) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn lead";
      btn.textContent = lead.label;
      btn.disabled = busy;
      btn.addEventListener("click", () => onLead(lead.id));
      leads.appendChild(btn);
    }
  }

  const sheet = state.deduction_sheet || {};
  $("deduction-prompt").textContent = sheet.prompt || "";

  const form = $("deduction-form");
  form.innerHTML = "";
  for (const field of sheet.fields || []) {
    const wrap = document.createElement("label");
    wrap.className = "deduction-field";
    wrap.innerHTML = `<span class="field-label">${field.label}</span>`;
    const select = document.createElement("select");
    select.name = field.id;
    select.required = true;
    select.innerHTML = '<option value="">Choose…</option>';
    for (const opt of field.options || []) {
      const o = document.createElement("option");
      o.value = opt;
      o.textContent = opt;
      if (sheet.answers?.[field.id] === opt) o.selected = true;
      select.appendChild(o);
    }
    wrap.appendChild(select);
    form.appendChild(wrap);
  }

  const resultEl = $("deduction-result");
  if (sheet.result) {
    resultEl.hidden = false;
    const lines = sheet.result.fields
      .map((f) => `${f.correct ? "✓" : "✗"} ${f.label}`)
      .join("<br/>");
    resultEl.innerHTML = `<p><strong>${sheet.result.all_correct ? "Deduction accepted." : "Some fields need revision."}</strong></p>${lines}`;
  } else {
    resultEl.hidden = true;
    resultEl.innerHTML = "";
  }

  const search = state.search || {};
  $("search-status").textContent = search.query
    ? `${search.count || 0} match(es) for “${search.query}”`
    : "Search unlocked artifact text";

  if (state.reveal) {
    showReveal(state.reveal, "reveal-panel");
  } else {
    const panel = $("reveal-panel");
    if (panel) {
      panel.hidden = true;
      panel.classList.remove("visible");
    }
  }
}

function renderBeatCase(state, { animate = true }) {
  $("cabinet-layout").hidden = true;
  $("beat-layout").hidden = false;
  $("search-console").hidden = true;

  const pack = state.pack;
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
      el.innerHTML = `<div class="type">${card.clue_type}</div><h3>${card.title}</h3><p>${card.detail}</p>`;
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
      tag.innerHTML = `<em>${ent.type}</em>${ent.value}`;
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
      btn.disabled = busy;
      btn.addEventListener("click", () => onLead(lead.id));
      leads.appendChild(btn);
    }
  }

  const trail = state.history?.length
    ? state.history.map((h) => `${h.beat}: ${h.label}`).join(" → ")
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

function showReveal(text, panelId = "reveal-panel") {
  const panel = $(panelId);
  if (!panel) return;
  panel.hidden = false;
  panel.classList.add("visible");
  panel.innerHTML = `<div class="reveal-inner">${renderMarkdownish(text)}</div>`;
}

function updateGenerationBadge(gen) {
  const badge = $("generation-badge");
  if (!gen || !gen.source) {
    badge.hidden = true;
    return;
  }
  badge.hidden = false;
  const labels = {
    cache: "Cached cabinet",
    live: "Live model",
    heuristic: "Heuristic cabinet",
    fallback: "Cached fallback",
  };
  badge.textContent = labels[gen.source] || gen.source;
  badge.className = `generation-badge source-${gen.source}`;
  if (gen.live_error) {
    badge.title = gen.live_error;
  }
}

async function loadCatalog() {
  catalog = await callApi("catalog");
  const sel = $("case-select");
  sel.innerHTML = "";
  for (const c of catalog) {
    const opt = document.createElement("option");
    opt.value = c.id;
    const modeTag = c.mode === "evidence_cabinet" ? " · cabinet" : "";
    opt.textContent = c.hero ? `★ ${c.title}${modeTag}` : `${c.title}${modeTag}`;
    opt.title = c.tagline || c.title;
    sel.appendChild(opt);
  }
}

async function loadGallery() {
  const items = await callApi("gallery_catalog");
  const grid = $("gallery-grid");
  grid.innerHTML = "";
  if (!items.length) {
    grid.innerHTML = '<p class="empty-state">No gallery clippings bundled.</p>';
    return;
  }
  for (const item of items) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "gallery-card";
    btn.setAttribute("role", "listitem");
    btn.setAttribute("aria-label", item.headline);
    btn.title = item.headline;
    const thumb = item.thumb_url
      ? `<img src="${item.thumb_url}" alt="" class="gallery-thumb" />`
      : '<span class="gallery-thumb placeholder">?</span>';
    btn.innerHTML = `
      ${thumb}
      <span class="gallery-meta">${item.date || ""}</span>
      <span class="gallery-headline">${item.headline}</span>
      <span class="gallery-score">mystery ${Math.round((item.mystery_score || 0) * 100)}%</span>
    `;
    btn.addEventListener("click", () => onGenerateGallery(item.id, false));
    grid.appendChild(btn);
  }
}

async function onGenerateGallery(clippingId, regenerate) {
  if (busy) return;
  setBusy(true, regenerate ? "Regenerating via hosted model…" : "Building Evidence Cabinet…");
  $("board").hidden = true;
  try {
    const state = await callApi("generate_from_gallery", clippingId, regenerate);
    sessionId = state.session_id;
    $("generate-panel").hidden = true;
    renderState(state);
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function onUploadGenerate(event) {
  event.preventDefault();
  if (busy) return;
  const fileInput = $("upload-image");
  const file = fileInput.files?.[0];
  if (!file) return;
  setBusy(true, "Reading upload & generating cabinet…");
  $("board").hidden = true;
  try {
    const b64 = await fileToBase64(file);
    const title = $("upload-title").value.trim() || "Uploaded clipping";
    const rawOcr = $("upload-ocr").value.trim();
    const regenerate = $("upload-regenerate").checked;
    const state = await callApi("generate_from_upload", b64, title, rawOcr, regenerate);
    sessionId = state.session_id;
    $("generate-panel").hidden = true;
    renderState(state);
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function startCase(caseId) {
  setBusy(true, "Opening case file…");
  $("board").hidden = true;
  $("generate-panel").hidden = true;
  for (const id of ["reveal-panel", "beat-reveal-panel"]) {
    const revealPanel = $(id);
    if (revealPanel) {
      revealPanel.hidden = true;
      revealPanel.classList.remove("visible");
      revealPanel.innerHTML = "";
    }
  }
  try {
    const state = await callApi("start_case", caseId);
    sessionId = state.session_id;
    renderState(state);
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function onLead(leadId) {
  if (!sessionId || busy) return;
  setBusy(true, "Following lead…");
  try {
    const state = await callApi("choose_lead", sessionId, leadId);
    renderState(state);
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function onSelectArtifact(artifactId) {
  if (!sessionId || busy) return;
  setBusy(true, "Opening artifact…");
  try {
    const state = await callApi("select_artifact", sessionId, artifactId);
    renderState(state, { animate: false });
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function onSearch(event) {
  event.preventDefault();
  if (!sessionId || busy) return;
  const query = $("search-input").value;
  setBusy(true, "Searching evidence…");
  try {
    const state = await callApi("search_case", sessionId, query);
    renderState(state, { animate: false });
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function onDeduction(event) {
  event.preventDefault();
  if (!sessionId || busy) return;
  const form = event.target;
  const answers = {};
  for (const field of form.elements) {
    if (field.name) answers[field.name] = field.value;
  }
  setBusy(true, "Checking deduction…");
  try {
    const state = await callApi("submit_deduction", sessionId, answers);
    renderState(state, { animate: false });
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function onReveal() {
  if (!sessionId || busy) return;
  setBusy(true, "Cross-checking archive…");
  try {
    const state = await callApi("reveal", sessionId);
    renderState(state, { animate: false });
    const panel = $("reveal-panel") || $("beat-reveal-panel");
    if (panel && !panel.hidden) {
      panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

async function init() {
  try {
    await loadCatalog();
    await loadGallery();
    const sel = $("case-select");
    sel.addEventListener("change", () => startCase(sel.value));
    $("btn-reset").addEventListener("click", () => {
      if (currentState?.generation) {
        $("generate-panel").hidden = false;
        $("board").hidden = true;
        setBusy(false);
        updateGenerationBadge(null);
        sessionId = null;
        currentState = null;
      } else {
        startCase(sel.value);
      }
    });
    $("btn-reveal").addEventListener("click", onReveal);
    $("btn-beat-reveal").addEventListener("click", onReveal);
    $("search-form").addEventListener("submit", onSearch);
    $("deduction-form").addEventListener("submit", onDeduction);
    $("upload-form").addEventListener("submit", onUploadGenerate);
    setBusy(false);
    if (!catalog.length) {
      showError("No case files found in data/cases/");
    }
  } catch (err) {
    setBusy(false);
    showError(err.message || String(err));
  }
}

init();
