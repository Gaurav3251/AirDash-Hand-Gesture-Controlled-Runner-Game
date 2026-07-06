"""
session_logger: persists session metadata and per-frame/per-event data to
SQLite. This is what turns the project from "looked like it worked" into
something with measurable evidence — evaluation_service reads what this
module writes.
"""
import os
import sqlite3
import time
from contextlib import closing

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_mode TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL,
    completed INTEGER DEFAULT 0,
    final_score INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    predicted_gesture TEXT,
    confidence REAL,
    action_fired TEXT,
    fps REAL,
    latency_ms REAL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
"""


class SessionLogger:
    def __init__(self, db_path=config.DB_PATH):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_schema()
        self.session_id = None

    def _init_schema(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    def start_session(self, input_mode):
        with closing(sqlite3.connect(self.db_path)) as conn:
            cur = conn.execute(
                "INSERT INTO sessions (input_mode, start_time) VALUES (?, ?)",
                (input_mode, time.time()),
            )
            conn.commit()
            self.session_id = cur.lastrowid
        return self.session_id

    def log_event(self, predicted_gesture=None, confidence=None,
                   action_fired=None, fps=None, latency_ms=None):
        if self.session_id is None:
            raise RuntimeError("start_session() must be called before log_event().")
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                """INSERT INTO events
                   (session_id, timestamp, predicted_gesture, confidence,
                    action_fired, fps, latency_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (self.session_id, time.time(), predicted_gesture, confidence,
                 action_fired, fps, latency_ms),
            )
            conn.commit()

    def end_session(self, completed=True, final_score=0):
        if self.session_id is None:
            return
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.execute(
                "UPDATE sessions SET end_time = ?, completed = ?, final_score = ? WHERE id = ?",
                (time.time(), int(completed), final_score, self.session_id),
            )
            conn.commit()
