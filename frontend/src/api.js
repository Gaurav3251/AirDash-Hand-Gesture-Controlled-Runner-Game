// api.js: thin wrapper around the FastAPI backend (backend/api.py).
// Base URL is separated out here so it's the one place to change if you
// deploy the backend somewhere other than localhost.
const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function getJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

async function postJSON(path, payload) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export function fetchSessions() {
  return getJSON("/api/sessions");
}

export function fetchSessionSummary(sessionId) {
  return getJSON(sessionId ? `/api/sessions/${sessionId}` : "/api/sessions/latest");
}

export function createSession(inputMode = "gesture") {
  return postJSON("/api/sessions", { input_mode: inputMode });
}

export function finalizeSession(sessionId, completed, finalScore, events) {
  return postJSON(`/api/sessions/${sessionId}/finalize`, {
    completed,
    final_score: finalScore,
    events,
  });
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function clearAllSessions() {
  const res = await fetch(`${API_BASE}/api/sessions`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}
