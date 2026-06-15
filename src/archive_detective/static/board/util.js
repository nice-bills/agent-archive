/** DOM + formatting helpers */

export const $ = (id) => document.getElementById(id);

export const DEBUG = new URLSearchParams(window.location.search).has("debug");

export const KIND_LABELS = {
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

export function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function renderMarkdownish(text) {
  if (!text) return "";
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br/>");
}

export function kindLabel(kind) {
  return KIND_LABELS[kind] || kind;
}

export function kindClass(kind) {
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
