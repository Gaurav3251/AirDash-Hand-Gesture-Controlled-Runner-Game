"""
backend/api.py: small read-only REST API exposing logged session and
evaluation data (from src/session_logger.py + src/evaluation_service.py) to
the React frontend. This does NOT run the game itself — the game is a
native pygame window (it needs direct webcam + low-latency rendering
access, which a browser tab doesn't have for a Python desktop app).

What this API is for: letting the React dashboard show session history and
evaluation metrics (accuracy proxy, false-trigger rate, latency, FPS,
lives/score) after you play, without touching SQLite directly from JS.

Run:
    uvicorn backend.api:app --reload --port 8000

Endpoints:
    GET /api/health
    GET /api/sessions
    GET /api/sessions/latest
    GET /api/sessions/{session_id}
"""
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import config
from src.evaluation_service import evaluate_session, list_sessions
from src.session_logger import SessionLogger

app = FastAPI(title="Gesture Gaming MVP API", version="1.0.0")

# Instantiating SessionLogger runs its schema migration (CREATE TABLE IF NOT
# EXISTS ...), so the sessions/events tables exist even if the API starts
# before main.py has ever been run once. Without this, /api/sessions would
# 500 on a fresh checkout instead of returning an empty list.
SessionLogger()

app.add_middleware(
    CORSMiddleware,
    # Vite's default dev server origin, plus 127.0.0.1 in case the browser
    # resolves localhost differently. Add your deployed frontend origin here
    # too once you deploy (e.g. a Vercel URL) instead of using "*".
    allow_origins=[config.FRONTEND_DEV_ORIGIN, "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/sessions")
def get_sessions():
    rows = list_sessions()
    return [
        {
            "id": session_id,
            "input_mode": input_mode,
            "start_time": start_time,
            "completed": bool(completed),
            "final_score": final_score,
        }
        for session_id, input_mode, start_time, completed, final_score in rows
    ]


@app.get("/api/sessions/latest")
def get_latest_session_summary():
    try:
        summary = evaluate_session(session_id=None)
    except ValueError:
        # No sessions logged yet — not an error, just nothing to show.
        return None
    return asdict(summary)


@app.get("/api/sessions/{session_id}")
def get_session_summary(session_id: int):
    try:
        summary = evaluate_session(session_id=session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return asdict(summary)
