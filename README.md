# AirDash — Runner with Lives, Stars, and a React Dashboard

Webcam-based gesture controller for a lane-dodging runner game. A person
sprite runs down 3 lanes, dodging obstacles using swipe/slide motion
gestures, with a 3-life system and star powerups. A FastAPI backend + React
frontend give you a live post-session evaluation dashboard.

## Project structure

```
AirDash/
├── main.py                    # Entry point — wires the full CV pipeline together
├── config.py                  # Every tunable constant lives here
├── src/
│   ├── camera_service.py      # Webcam capture, frame rate control
│   ├── hand_tracker.py        # MediaPipe hand landmark extraction
│   ├── feature_extractor.py   # Landmark geometry -> feature vector
│   ├── gesture_classifier.py  # Rule-based STATIC gestures (palm/fist/thumbs)
│   ├── motion_gesture_detector.py  # Rule-based DYNAMIC gestures (swipe/slide)
│   ├── stability_filter.py    # Temporal smoothing/debounce for static gestures
│   ├── calibration_engine.py  # Pre-game camera/lighting/hand checks
│   ├── game_controller.py     # Gesture/keyboard -> game action mapping
│   ├── session_logger.py      # SQLite event/session logging
│   ├── evaluation_service.py  # Computes accuracy/latency/FPS metrics
│   └── ui_overlay.py          # Draws gesture/confidence/calibration overlay
├── game/
│   ├── entities.py            # Player (person sprite), Obstacle, Star
│   └── game_app.py            # Pygame lane-dodging runner: lives, duck, stars
├── backend/
│   └── api.py                 # FastAPI read-only API over session/eval data
├── frontend/                  # React + Vite dashboard (talks to backend/api.py)
├── scripts/
│   └── run_evaluation.py      # CLI post-session evaluation summary
├── tests/
│   └── test_gesture_classifier.py
├── data/logs/                 # SQLite db lives here (gitignored)
├── requirements.txt
└── .gitignore
```

## Setup — Python game

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Note:** MediaPipe's legacy `mp.solutions` API (used by `hand_tracker.py`)
does not have wheels for Python 3.13 yet. Use **Python 3.10 or 3.11** for
this project, or you'll hit `AttributeError: module 'mediapipe' has no
attribute 'solutions'` on startup.

### Running the game

```bash
python main.py --input keyboard          # test the game itself, no camera
python main.py --input gesture           # full pipeline with your webcam
python main.py --input gesture --skip-calibration
```

## Gesture vocabulary

| Gesture | Type | Action |
|---|---|---|
| Swipe left / right | motion | Change lane |
| Slide up | motion | Jump — clears **ground** obstacles (cones, potholes) |
| Slide down | motion | Duck — clears **overhead** obstacles (barriers) |
| Open palm (held) | static | Pause / resume / restart |
| Fist (held) | static | **Stop** — ends the run immediately (distinct from pause) |
| Thumbs up (held) | static | +1 life (capped at 3) |

**Hand shape doesn't matter for swipe/slide** — the detector tracks where
your palm *is* over a short time window, not what shape it's making. Keep
your hand naturally open (fingers visible enough for MediaPipe to find
landmarks) and just move it — no need for a "handshake" or "pledge"
position. What matters is:
- Move with enough speed/distance (roughly 10-15% of the frame width in
  under half a second — a normal deliberate hand movement, not a slow drift).
- Keep the motion mostly along one axis — swipe left/right stays roughly
  level, slide up/down stays roughly vertical. A diagonal motion can get
  rejected as "off-axis drift" (tunable via `MOTION_MAX_CROSS_AXIS_DRIFT`
  in `config.py`).
- Keep your hand inside the frame and reasonably lit — MediaPipe loses
  tracking on fast motion blur or when the hand exits frame edges, which
  breaks the motion history mid-swipe.

**Debug tip:** the camera preview (top-right picture-in-picture during
gesture mode) now draws a yellow trail following your palm's recent path,
and the terminal prints `[gesture] swipe_right fired (confidence=0.63)`
every time a motion gesture actually registers. If you move your hand and
see the trail but never see a console print, the motion isn't crossing the
displacement/confidence threshold — try a bigger, faster, straighter
motion. If you don't even see the trail, MediaPipe isn't tracking your
hand at all (check lighting/framing).

**Static gestures use a separate detector** (`gesture_classifier.py`) that
only looks at your hand's current shape (curled = fist, spread = open palm,
thumb-only = thumbs up) — position doesn't matter for these, only shape,
and they require holding the pose steady for a few frames before firing
(this is the stability filter, so a passing pose doesn't accidentally
trigger pause/stop).



**Keyboard mode:** Left/Right = lane, Up = jump, Down = duck, P = pause/restart,
X = stop, L = +1 life.

## Game mechanics

- **3 lives per session.** Getting hit by an obstacle you didn't avoid
  costs 1 life and grants ~1.2s of invincibility (the player sprite flickers
  during this window). Life reaches 0 → game over.
- **Obstacles are categorized**: ground obstacles (cone, pothole) are
  avoided by jumping; overhead obstacles (barrier) are avoided by ducking.
  This is what makes both gestures actually matter instead of jump being a
  strictly-better substitute for duck.
- **Stars** fall periodically; catching one adds bonus points and doubles
  your score rate for 10 seconds.
- **Fist immediately ends the run** (`ACTION_STOP`), separate from open-palm
  pause/resume. If you meant something different by "closed fist to stop" —
  e.g. a hard quit to the OS instead of ending the run — that's a one-line
  change in `game_controller.py`.


## Backend + frontend architecture

**Important scope note:** the backend/frontend here is a **post-session
evaluation dashboard**, not a browser-playable version of the game. The
game itself stays a native Python/pygame window, because it needs direct,
low-latency webcam access — a browser tab can't drive `cv2.VideoCapture` +
pygame's render loop. Porting actual gameplay into the browser would mean
re-implementing hand tracking in JS (e.g. MediaPipe Tasks for Web) and the
whole game loop in Canvas/WebGL — a much bigger rewrite than "add a
frontend," and out of MVP scope. What's built here is the practical
version: play in the native window, review results in the browser.

```
[main.py + pygame window]  --writes-->  [SQLite: data/logs/sessions.db]
                                                     ^
                                                     |  reads
                                        [backend/api.py — FastAPI]
                                                     ^
                                                     |  fetch()
                                        [frontend/ — React + Vite]
```

### Run the backend

```bash
pip install -r requirements.txt   # includes fastapi + uvicorn now
uvicorn backend.api:app --reload --port 8000
```

Endpoints:
- `GET /api/health`
- `GET /api/sessions` — list all sessions
- `GET /api/sessions/latest` — most recent session's evaluation summary
- `GET /api/sessions/{id}` — a specific session's evaluation summary

### Run the frontend

```bash
cd frontend
npm install
npm run dev        # opens on http://localhost:5173
```

The frontend calls `http://localhost:8000` by default (see
`frontend/src/api.js`); override with a `VITE_API_BASE` env var if you
deploy the backend elsewhere.

Run backend and frontend in two terminals, alongside `python main.py
--input gesture` in a third. Play a session, then refresh the dashboard.

## Evaluation (CLI alternative to the dashboard)

```bash
python scripts/run_evaluation.py
python scripts/run_evaluation.py --session-id 3
python scripts/run_evaluation.py --list
```

## License
See [LICENSE](LICENSE.txt)
