"""
evaluation_service: reads session/event data logged by session_logger and
computes the metrics called for in the proposal — recognition accuracy
proxy, false-trigger rate, latency, FPS, and completion status. This is
what scripts/run_evaluation.py prints after a play session.

Note on "accuracy": without ground-truth labels (a human confirming which
gesture was intended each frame), true recognition accuracy can't be
computed from logs alone. This module reports a practical proxy — the
fraction of high-confidence predictions that actually passed the stability
filter and fired a command — which is the right signal for judging
pipeline reliability. Swap in labeled-recording accuracy in Phase 2 if
you build a labeled test set (see data/recordings/).
"""
import sqlite3
from contextlib import closing
from dataclasses import dataclass

import config


@dataclass
class EvaluationSummary:
    session_id: int
    input_mode: str
    duration_seconds: float
    completed: bool
    final_score: int
    total_frames: int
    fired_commands: int
    stable_prediction_rate: float   # proxy accuracy: fired / high-confidence frames
    false_trigger_rate_per_min: float
    avg_latency_ms: float
    avg_fps: float
    meets_accuracy_target: bool
    meets_false_trigger_target: bool
    meets_latency_target: bool
    meets_fps_target: bool


def _fetch_session(conn, session_id):
    row = conn.execute(
        "SELECT id, input_mode, start_time, end_time, completed, final_score "
        "FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    return row


def _latest_session_id(conn):
    row = conn.execute("SELECT id FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None


def evaluate_session(session_id=None, db_path=config.DB_PATH) -> EvaluationSummary:
    with closing(sqlite3.connect(db_path)) as conn:
        if session_id is None:
            session_id = _latest_session_id(conn)
        if session_id is None:
            raise ValueError("No sessions found in the database yet.")

        session_row = _fetch_session(conn, session_id)
        if session_row is None:
            raise ValueError(f"No session found with id {session_id}.")

        _, input_mode, start_time, end_time, completed, final_score = session_row
        duration = (end_time or start_time) - start_time

        events = conn.execute(
            "SELECT predicted_gesture, confidence, action_fired, fps, latency_ms "
            "FROM events WHERE session_id = ?", (session_id,)
        ).fetchall()

    total_frames = len(events)
    high_confidence_frames = [
        e for e in events
        if e[1] is not None and e[1] >= config.MIN_CONFIDENCE_THRESHOLD
        and e[0] != config.GESTURE_NONE
    ]
    fired_events = [e for e in events if e[2] and e[2] != config.ACTION_NONE]

    stable_prediction_rate = (
        len(fired_events) / len(high_confidence_frames)
        if high_confidence_frames else 0.0
    )

    # "False trigger" proxy: a command fired while predicted gesture confidence
    # was below threshold (i.e. the stability filter's window smoothed over
    # noise but the underlying signal was weak) — the closest signal available
    # without human-labeled ground truth.
    false_triggers = [
        e for e in fired_events
        if e[1] is not None and e[1] < config.MIN_CONFIDENCE_THRESHOLD
    ]
    duration_minutes = max(duration / 60.0, 1e-6)
    false_trigger_rate = len(false_triggers) / duration_minutes

    latencies = [e[4] for e in events if e[4] is not None]
    avg_latency_ms = sum(latencies) / len(latencies) if latencies else 0.0

    fps_values = [e[3] for e in events if e[3] is not None]
    avg_fps = sum(fps_values) / len(fps_values) if fps_values else 0.0

    return EvaluationSummary(
        session_id=session_id,
        input_mode=input_mode,
        duration_seconds=duration,
        completed=bool(completed),
        final_score=final_score,
        total_frames=total_frames,
        fired_commands=len(fired_events),
        stable_prediction_rate=stable_prediction_rate,
        false_trigger_rate_per_min=false_trigger_rate,
        avg_latency_ms=avg_latency_ms,
        avg_fps=avg_fps,
        meets_accuracy_target=stable_prediction_rate >= config.TARGET_ACCURACY,
        meets_false_trigger_target=false_trigger_rate <= config.TARGET_MAX_FALSE_TRIGGERS_PER_MIN,
        meets_latency_target=avg_latency_ms <= config.TARGET_MAX_LATENCY_MS,
        meets_fps_target=avg_fps >= config.TARGET_MIN_FPS,
    )


def list_sessions(db_path=config.DB_PATH):
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            "SELECT id, input_mode, start_time, completed, final_score "
            "FROM sessions ORDER BY id DESC"
        ).fetchall()
    return rows
