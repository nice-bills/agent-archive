/** Gradio client API helpers */
import { Client } from "https://cdn.jsdelivr.net/npm/@gradio/client/dist/index.min.js";

let clientPromise = null;

function getClient() {
  if (!clientPromise) {
    clientPromise = Client.connect(window.location.origin);
  }
  return clientPromise;
}

function apiPath(name) {
  return name.startsWith("/") ? name : `/${name}`;
}

function unwrapResult(result) {
  if (result == null) return result;
  const data = result.data ?? result;
  if (Array.isArray(data)) return data[0];
  return data;
}

function extractGradioError(message) {
  const data = message?.data ?? message?.output ?? message;
  if (typeof data === "string" && data.trim()) return data.trim();
  if (Array.isArray(data)) {
    const first = data.find((item) => typeof item === "string" && item.trim());
    if (first) return first.trim();
    if (data[0]?.error) return String(data[0].error);
  }
  if (data && typeof data === "object") {
    if (data.error) return String(data.error);
    if (data.message) return String(data.message);
  }
  return message?.message || "Generation failed on the server";
}

function emptyResponseMessage(name) {
  const onSpace = /\.hf\.space$/.test(window.location.hostname);
  if (name.includes("upload")) {
    if (onSpace) {
      return (
        "Upload generation lost connection — the Space may still be building or restarting, " +
        "or the GPU run timed out. Paste OCR text to skip vision, wait for Running status, " +
        "or pick a gallery polaroid for instant play."
      );
    }
    return "Upload generation returned no data — the server may have timed out or restarted.";
  }
  if (onSpace) {
    return (
      "Generation lost connection — wait until the Space shows Running, reload, " +
      "or pick a polaroid with a pre-built cabinet."
    );
  }
  return `${name} returned no data`;
}

export function assertApiSession(value, name) {
  if (value && value.ok === false) {
    const err = new Error(value.error || "Generation failed");
    err.code = value.error_code || "generation_failed";
    throw err;
  }
  if (value === undefined || value === null) {
    throw new Error(emptyResponseMessage(name));
  }
  if (!value.session_id) {
    const err = new Error(value.error || emptyResponseMessage(name));
    err.code = value.error_code || "no_session";
    throw err;
  }
  return value;
}

export async function callApi(name, ...args) {
  const app = await getClient();
  const result = await app.predict(apiPath(name), args);
  const value = unwrapResult(result);
  if (value === undefined) {
    throw new Error(emptyResponseMessage(name));
  }
  return value;
}

export async function callApiQueued(name, args, onStatus) {
  const app = await getClient();
  const job = app.submit(apiPath(name), args);
  let payload;
  let streamError;
  for await (const message of job) {
    if (message.type === "status" && onStatus) {
      onStatus(message);
    } else if (message.type === "error" || message.success === false) {
      streamError = extractGradioError(message);
    } else if (message.data !== undefined) {
      payload = message;
    }
  }
  if (streamError) {
    const err = new Error(streamError);
    err.code = "server_error";
    throw err;
  }
  const value = unwrapResult(payload);
  return assertApiSession(value, name);
}

export function onQueueStatus(message) {
  const st = message.status ?? message;
  const line = document.getElementById("archivist-line");
  if (!line || st.position == null || !st.queue_size || st.queue_size <= 1) return;
  line.textContent = `Waiting in queue… spot ${st.position + 1} of ${st.queue_size}`;
}
