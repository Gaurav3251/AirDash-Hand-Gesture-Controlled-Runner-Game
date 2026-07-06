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

export function fetchSessions() {
  return getJSON("/api/sessions");
}

export function fetchSessionSummary(sessionId) {
  return getJSON(sessionId ? `/api/sessions/${sessionId}` : "/api/sessions/latest");
}

