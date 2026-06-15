/** Shared client session state */
export let sessionId = null;
export let catalog = [];
export let galleryItems = [];
export let busy = false;
export let currentState = null;
export let modelInfo = null;
export let archivistTimer = null;
export let archivistLineIdx = 0;
export let elapsedTimer = null;
export let activeClippingId = null;

export function setSessionId(id) {
  sessionId = id;
}
export function setCatalog(items) {
  catalog = items;
}
export function setGalleryItems(items) {
  galleryItems = items;
}
export function setBusyState(on) {
  busy = on;
}
export function setCurrentState(state) {
  currentState = state;
}
export function setModelInfo(info) {
  modelInfo = info;
}

export function setArchivistTimer(timer) {
  archivistTimer = timer;
}

export function setArchivistLineIdx(idx) {
  archivistLineIdx = idx;
}

export function bumpArchivistLineIdx(mod) {
  archivistLineIdx = (archivistLineIdx + 1) % mod;
  return archivistLineIdx;
}

export function setElapsedTimer(timer) {
  elapsedTimer = timer;
}

export function setActiveClippingId(id) {
  activeClippingId = id;
}
