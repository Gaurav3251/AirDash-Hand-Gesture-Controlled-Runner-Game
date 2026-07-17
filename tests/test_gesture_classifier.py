"""
Unit tests for gesture_classifier, motion_gesture_detector, stability_filter,
and core game entity logic (lives, ducking, obstacle categories) — all using
synthetic data, no webcam/MediaPipe/display needed. Run with:
    pytest tests/
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from src import config
from src.feature_extractor import extract_features
from src.gesture_classifier import classify
from src.motion_gesture_detector import MotionGestureDetector
from src.stability_filter import StabilityFilter


def _make_landmarks(wrist=(0.5, 0.7), tip_offsets=None, z=0.0):
    """
    Builds a minimal synthetic 21-point landmark list. tip_offsets lets tests
    push individual fingertips out/in relative to the wrist to simulate
    extension or curl. All non-tip/mcp points are placed near the wrist —
    fine for these rules, which only inspect wrist, MCPs, and tips.
    """
    tip_offsets = tip_offsets or {}
    points = [wrist] * 21  # default: everything collapsed near the wrist (= curled)
    points = list(points)
    mcp_indices = [2, 5, 9, 13, 17]
    tip_indices = [4, 8, 12, 16, 20]

    for mcp_idx in mcp_indices:
        points[mcp_idx] = (wrist[0], wrist[1] - 0.05)  # MCPs slightly above wrist

    for tip_idx in tip_indices:
        dx, dy = tip_offsets.get(tip_idx, (0.0, -0.05))
        points[tip_idx] = (wrist[0] + dx, wrist[1] + dy)

    return [(x, y, z) for x, y in points]


# --- static gesture classifier ---

def test_fist_classified_when_all_fingers_curled():
    landmarks = _make_landmarks(
        wrist=(0.5, 0.7),
        tip_offsets={4: (0.0, -0.01), 8: (0.0, -0.01), 12: (0.0, -0.01),
                     16: (0.0, -0.01), 20: (0.0, -0.01)},
    )
    features = extract_features(landmarks)
    label, confidence = classify(features)
    assert label == config.GESTURE_FIST
    assert confidence > 0.5


def test_open_palm_classified_when_fingers_extended():
    landmarks = _make_landmarks(
        wrist=(0.5, 0.7),
        tip_offsets={4: (0.0, -0.3), 8: (0.0, -0.3), 12: (0.0, -0.3),
                     16: (0.0, -0.3), 20: (0.0, -0.3)},
    )
    features = extract_features(landmarks)
    label, confidence = classify(features)
    assert label == config.GESTURE_OPEN_PALM
    assert confidence > 0.5


def test_thumbs_up_classified_for_thumb_only_extended():
    landmarks = _make_landmarks(
        wrist=(0.5, 0.7),
        tip_offsets={4: (-0.24, -0.12), 8: (0.0, -0.01), 12: (0.0, -0.01),
                     16: (0.0, -0.01), 20: (0.0, -0.01)},
    )
    features = extract_features(landmarks)
    label, _ = classify(features)
    assert label == config.GESTURE_THUMBS_UP


# --- motion gesture detector (swipe / slide) ---

def test_swipe_right_detected_from_rightward_motion():
    detector = MotionGestureDetector(
        history_seconds=1.0, min_displacement=0.1,
        max_cross_axis_drift=0.15, min_confidence=0.1, cooldown_seconds=0.0,
    )
    fired = []
    for x in [0.2, 0.3, 0.4, 0.5, 0.6]:
        features = extract_features(_make_landmarks(wrist=(x, 0.6)))
        label, confidence = detector.update(features)
        if label != config.GESTURE_NONE:
            fired.append((label, confidence))
    assert any(label == config.GESTURE_SWIPE_RIGHT for label, _ in fired)


def test_swipe_left_detected_from_leftward_motion():
    detector = MotionGestureDetector(
        history_seconds=1.0, min_displacement=0.1,
        max_cross_axis_drift=0.15, min_confidence=0.1, cooldown_seconds=0.0,
    )
    fired = []
    for x in [0.6, 0.5, 0.4, 0.3, 0.2]:
        features = extract_features(_make_landmarks(wrist=(x, 0.6)))
        label, confidence = detector.update(features)
        if label != config.GESTURE_NONE:
            fired.append((label, confidence))
    assert any(label == config.GESTURE_SWIPE_LEFT for label, _ in fired)


def test_slide_down_detected_from_downward_motion():
    detector = MotionGestureDetector(
        history_seconds=1.0, min_displacement=0.1,
        max_cross_axis_drift=0.15, min_confidence=0.1, cooldown_seconds=0.0,
    )
    fired = []
    for y in [0.2, 0.3, 0.4, 0.5, 0.6]:
        features = extract_features(_make_landmarks(wrist=(0.5, y)))
        label, confidence = detector.update(features)
        if label != config.GESTURE_NONE:
            fired.append((label, confidence))
    assert any(label == config.GESTURE_SLIDE_DOWN for label, _ in fired)


def test_slide_up_detected_from_upward_motion():
    detector = MotionGestureDetector(
        history_seconds=1.0, min_displacement=0.1,
        max_cross_axis_drift=0.15, min_confidence=0.1, cooldown_seconds=0.0,
    )
    fired = []
    for y in [0.6, 0.5, 0.4, 0.3, 0.2]:
        features = extract_features(_make_landmarks(wrist=(0.5, y)))
        label, confidence = detector.update(features)
        if label != config.GESTURE_NONE:
            fired.append((label, confidence))
    assert any(label == config.GESTURE_SLIDE_UP for label, _ in fired)


# --- stability filter (static gestures only) ---

def test_stability_filter_requires_window_before_firing():
    sf = StabilityFilter(window_size=5, min_agreement=0.6, min_confidence=0.5)
    for _ in range(4):
        result = sf.update(config.GESTURE_FIST, 0.9)
        assert result is None  # window not full yet
    result = sf.update(config.GESTURE_FIST, 0.9)
    assert result == config.GESTURE_FIST


def test_stability_filter_ignores_low_confidence_noise():
    sf = StabilityFilter(window_size=5, min_agreement=0.6, min_confidence=0.5)
    result = None
    for _ in range(10):
        result = sf.update(config.GESTURE_FIST, 0.2)  # below confidence floor
    assert result is None


def test_stability_filter_respects_cooldown():
    sf = StabilityFilter(window_size=3, min_agreement=0.6, min_confidence=0.5,
                          cooldown_seconds=10.0)
    for _ in range(3):
        first = sf.update(config.GESTURE_FIST, 0.9)
    assert first == config.GESTURE_FIST

    # Same gesture again immediately — should be suppressed by cooldown.
    for _ in range(3):
        second = sf.update(config.GESTURE_FIST, 0.9)
    assert second is None


# --- game entities: lives, ducking, obstacle categories ---

def test_player_loses_life_on_ground_obstacle_hit_without_jump():
    import pygame
    pygame.init()
    pygame.display.set_mode((100, 100))
    from game.game_app import GameApp
    from game.entities import Obstacle

    game = GameApp()
    game.obstacles = [Obstacle(lane=game.player.current_lane, speed=0, kind="cone")]
    game.obstacles[0].y = game.player.y  # force overlap
    game.update()
    assert game.lives == config.INITIAL_LIVES - 1
    pygame.quit()


def test_player_avoids_ground_obstacle_while_jumping():
    import time
    import pygame
    pygame.init()
    pygame.display.set_mode((100, 100))
    from game.game_app import GameApp
    from game.entities import Obstacle

    game = GameApp()
    game.player.jump()
    game.player._jump_start_time = time.time() - (config.JUMP_DURATION_MS / 1000) / 2  # mid-arc
    game.obstacles = [Obstacle(lane=game.player.current_lane, speed=0, kind="cone")]
    game.obstacles[0].y = game.player.y_base  # ground-level, player is airborne
    game.update()
    assert game.lives == config.INITIAL_LIVES
    pygame.quit()


def test_player_avoids_overhead_obstacle_while_ducking():
    import pygame
    pygame.init()
    pygame.display.set_mode((100, 100))
    from game.game_app import GameApp
    from game.entities import Obstacle

    game = GameApp()
    game.player.duck()
    game.obstacles = [Obstacle(lane=game.player.current_lane, speed=0, kind="barrier")]
    game.obstacles[0].y = game.player.y - game.obstacles[0].y_offset_for_category
    game.update()
    assert game.lives == config.INITIAL_LIVES
    pygame.quit()


def test_extra_life_action_caps_at_max_lives():
    import pygame
    pygame.init()
    pygame.display.set_mode((100, 100))
    from game.game_app import GameApp

    game = GameApp()
    game.apply_action(config.ACTION_EXTRA_LIFE)
    assert game.lives == config.MAX_LIVES  # already at max, should not exceed
    pygame.quit()


def test_stop_action_ends_game_immediately():
    import pygame
    pygame.init()
    pygame.display.set_mode((100, 100))
    from game.game_app import GameApp

    game = GameApp()
    game.apply_action(config.ACTION_STOP)
    assert game.game_over is True
    pygame.quit()


def test_star_pickup_grants_double_score_window():
    import pygame
    pygame.init()
    pygame.display.set_mode((100, 100))
    from game.game_app import GameApp
    from game.entities import Star

    game = GameApp()
    star = Star(lane=game.player.current_lane, speed=0)
    star.y = game.player.y
    game.stars = [star]
    game.update()
    assert game._is_double_score() is True
    pygame.quit()
