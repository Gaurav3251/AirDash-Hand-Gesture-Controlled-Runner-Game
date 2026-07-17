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

from src import config
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
    allow_methods=["*"],
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


@app.post("/api/sessions")
def create_session(data: dict = None):
    input_mode = "gesture"
    if data and "input_mode" in data:
        input_mode = data["input_mode"]
    
    logger = SessionLogger()
    session_id = logger.start_session(input_mode=input_mode)
    return {"session_id": session_id}


@app.post("/api/sessions/{session_id}/finalize")
def finalize_session(session_id: int, data: dict):
    completed = data.get("completed", False)
    final_score = data.get("final_score", 0)
    events = data.get("events", [])
    
    import sqlite3
    import time
    from contextlib import closing
    
    with closing(sqlite3.connect(config.DB_PATH)) as conn:
        # Update session
        conn.execute(
            "UPDATE sessions SET end_time = ?, completed = ?, final_score = ? WHERE id = ?",
            (time.time(), int(completed), final_score, session_id),
        )
        
        # Insert events
        if events:
            conn.executemany(
                """INSERT INTO events
                   (session_id, timestamp, predicted_gesture, confidence,
                    action_fired, fps, latency_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        session_id,
                        e.get("timestamp", time.time()),
                        e.get("predicted_gesture"),
                        e.get("confidence"),
                        e.get("action_fired"),
                        e.get("fps"),
                        e.get("latency_ms"),
                    )
                    for e in events
                ],
            )
        conn.commit()
        
    return {"status": "success", "session_id": session_id}


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: int):
    import sqlite3
    from contextlib import closing
    
    with closing(sqlite3.connect(config.DB_PATH)) as conn:
        conn.execute("DELETE FROM events WHERE session_id = ?", (session_id,))
        cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
            
    return {"status": "success", "message": f"Session {session_id} deleted."}


@app.delete("/api/sessions")
def clear_all_sessions():
    import sqlite3
    from contextlib import closing
    
    with closing(sqlite3.connect(config.DB_PATH)) as conn:
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM sessions")
        conn.commit()
        
    return {"status": "success", "message": "All sessions cleared."}
