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

export async function callApi(name, ...args) {
  const app = await getClient();
  const result = await app.predict(apiPath(name), args);
  const value = unwrapResult(result);
  if (value === undefined) {
    throw new Error(`${name} returned no data`);
  }
  return value;
}

export async function callApiQueued(name, args, onStatus) {
  const app = await getClient();
  const job = app.submit(apiPath(name), args);
  let payload;
  for await (const message of job) {
    if (message.type === "status" && onStatus) {
      onStatus(message);
    } else if (message.data !== undefined) {
      payload = message;
    }
  }
  const value = unwrapResult(payload);
  if (value === undefined) {
    throw new Error(`${name} returned no data`);
  }
  return value;
}

export function onQueueStatus(message) {
  const st = message.status ?? message;
  const line = document.getElementById("archivist-line");
  if (!line || st.position == null || !st.queue_size || st.queue_size <= 1) return;
  line.textContent = `Waiting in queue… spot ${st.position + 1} of ${st.queue_size}`;
}
