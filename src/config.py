"""
Central configuration. Every tunable constant used across the pipeline
lives here so behavior can be adjusted without touching module internals.
"""

# --- Camera ---
CAMERA_INDEX = 0
FRAME_WIDTH = 960
FRAME_HEIGHT = 540
TARGET_FPS = 30

# --- MediaPipe hand tracking ---
MAX_NUM_HANDS = 1
MIN_DETECTION_CONFIDENCE = 0.6
MIN_TRACKING_CONFIDENCE = 0.6

# --- Gesture classification ---
# Static poses (held, classified per-frame by gesture_classifier.py)
GESTURE_OPEN_PALM = "open_palm"
GESTURE_FIST = "fist"
GESTURE_THUMBS_UP = "thumbs_up"
# Dynamic poses (short motions, classified from a history window by
# motion_gesture_detector.py) — this is what drives lane change, jump, duck.
GESTURE_SWIPE_LEFT = "swipe_left"
GESTURE_SWIPE_RIGHT = "swipe_right"
GESTURE_SLIDE_UP = "slide_up"
GESTURE_SLIDE_DOWN = "slide_down"
GESTURE_NONE = "none"

STATIC_GESTURES = [
    GESTURE_OPEN_PALM,
    GESTURE_FIST,
    GESTURE_THUMBS_UP,
]
MOTION_GESTURES = [
    GESTURE_SWIPE_LEFT,
    GESTURE_SWIPE_RIGHT,
    GESTURE_SLIDE_UP,
    GESTURE_SLIDE_DOWN,
]
ALL_GESTURES = STATIC_GESTURES + MOTION_GESTURES

# Curl threshold: fraction of fingers considered "curled" to call it a fist
FIST_CURL_RATIO = 0.55
# Extension threshold: fraction of fingers considered "extended" for open palm
OPEN_PALM_EXTENSION_RATIO = 0.75

# --- Motion gesture detection (swipe / slide) ---
# Tracks palm-center position over a short rolling time window and fires a
# swipe/slide when it moved far enough in one direction without drifting
# too much off-axis. Hand SHAPE doesn't matter here — only its position —
# so any natural hand pose works as long as MediaPipe can keep tracking it.
MOTION_HISTORY_SECONDS = 0.6            # window of recent hand positions considered
MOTION_MIN_DISPLACEMENT = 0.11          # min movement (fraction of frame) to count as a swipe
MOTION_MAX_CROSS_AXIS_DRIFT = 0.20      # tolerance for imperfect diagonal movement
MOTION_MIN_CONFIDENCE = 0.5             # confidence floor to actually fire the command
MOTION_COOLDOWN_SECONDS = 0.35          # min time between repeated fires

# --- Stability filter (confidence smoothing + debounce + cooldown) ---
# Applies to STATIC gestures only — swipes/slides already have their own
# displacement + cooldown logic in motion_gesture_detector.py and would be
# muted out by an additional temporal-majority-vote window (a swipe is a
# single short event, not a held pose).
STABILITY_WINDOW_SIZE = 6          # frames considered for majority vote
STABILITY_MIN_AGREEMENT = 0.7      # fraction of window that must agree
MIN_CONFIDENCE_THRESHOLD = 0.65    # per-frame confidence floor
COMMAND_COOLDOWN_SECONDS = 0.35    # min time between repeated fires of same gesture

# --- Calibration ---
CALIBRATION_DURATION_SECONDS = 5
CALIBRATION_MIN_HAND_VISIBLE_RATIO = 0.8   # hand must be visible this % of calib window
CALIBRATION_MIN_BRIGHTNESS = 60            # mean pixel brightness (0-255)
CALIBRATION_MAX_BRIGHTNESS = 220

# --- Game ---
GAME_WINDOW_WIDTH = 800
GAME_WINDOW_HEIGHT = 600
GAME_FPS = 60
LANE_COUNT = 3
OBSTACLE_SPEED_START = 3.5  # Decreased from 6.0
OBSTACLE_SPEED_INCREMENT = 0.05  # Decreased from 0.15
OBSTACLE_SPAWN_INTERVAL_MS = 1500  # Increased from 1100
JUMP_DURATION_MS = 600  # Increased from 450
DUCK_DURATION_MS = 700  # Increased from 550

# Lives
INITIAL_LIVES = 3
MAX_LIVES = 3
INVINCIBILITY_AFTER_HIT_SECONDS = 1.2  # brief immunity window right after taking a hit

# Stars (double-score powerup)
STAR_SPAWN_INTERVAL_MS = 4000
STAR_SCORE_VALUE = 50           # bonus points for catching the star itself
STAR_DOUBLE_SCORE_SECONDS = 10.0

# --- Actions (game_controller vocabulary, independent of input source) ---
ACTION_MOVE_LEFT = "move_left"
ACTION_MOVE_RIGHT = "move_right"
ACTION_JUMP = "jump"
ACTION_DUCK = "duck"
ACTION_PAUSE = "pause"          # toggles pause/resume; restarts if game over
ACTION_STOP = "stop"            # immediately ends the current run
ACTION_EXTRA_LIFE = "extra_life"
ACTION_NONE = "none"

# Default gesture -> action mapping (kept configurable for Phase 2
# accessibility mode, where an alternate map could be swapped in).
DEFAULT_GESTURE_ACTION_MAP = {
    GESTURE_OPEN_PALM: ACTION_PAUSE,
    GESTURE_FIST: ACTION_STOP,
    GESTURE_SWIPE_LEFT: ACTION_MOVE_LEFT,
    GESTURE_SWIPE_RIGHT: ACTION_MOVE_RIGHT,
    GESTURE_SLIDE_UP: ACTION_JUMP,
    GESTURE_SLIDE_DOWN: ACTION_DUCK,
    GESTURE_THUMBS_UP: ACTION_EXTRA_LIFE,
}

# --- Logging / storage ---
DB_PATH = "sessions.db"  # DB path changed to root level sessions.db

# --- Evaluation targets (MVP bar from the proposal) ---
TARGET_ACCURACY = 0.85
TARGET_MAX_FALSE_TRIGGERS_PER_MIN = 2
TARGET_MAX_LATENCY_MS = 200
TARGET_MIN_FPS = 20

# --- UI overlay ---
OVERLAY_FONT_SCALE = 0.6
OVERLAY_PIP_WIDTH = 240   # picture-in-picture camera feed size inside game window
OVERLAY_PIP_HEIGHT = 180

# --- API / backend ---
API_HOST = "127.0.0.1"
API_PORT = 8000
FRONTEND_DEV_ORIGIN = "http://localhost:5173"
