"""
motion_gesture_detector: detects dynamic hand movements such as swipe left,
swipe right, slide up, and slide down from a short rolling history of palm
centers. This keeps motion gestures separate from static pose recognition
so Phase 1 can remain rule-based and trainable models can be added later.
"""
import time
from collections import deque

import config
from src.feature_extractor import HandFeatures


class MotionGestureDetector:
    def __init__(
        self,
        history_seconds=config.MOTION_HISTORY_SECONDS,
        min_displacement=config.MOTION_MIN_DISPLACEMENT,
        max_cross_axis_drift=config.MOTION_MAX_CROSS_AXIS_DRIFT,
        min_confidence=config.MOTION_MIN_CONFIDENCE,
        cooldown_seconds=config.MOTION_COOLDOWN_SECONDS,
    ):
        self.history_seconds = history_seconds
        self.min_displacement = min_displacement
        self.max_cross_axis_drift = max_cross_axis_drift
        self.min_confidence = min_confidence
        self.cooldown_seconds = cooldown_seconds
        self._history = deque()
        self._last_fired_time = 0.0

    def update(self, features: HandFeatures):
        now = time.time()
        self._history.append((now, features.palm_center_x, features.palm_center_y))

        while self._history and now - self._history[0][0] > self.history_seconds:
            self._history.popleft()

        if len(self._history) < 3 or now - self._last_fired_time < self.cooldown_seconds:
            return config.GESTURE_NONE, 0.0

        _, start_x, start_y = self._history[0]
        _, end_x, end_y = self._history[-1]
        dx = end_x - start_x
        dy = end_y - start_y

        label, confidence = self._classify_delta(dx, dy)
        if confidence < self.min_confidence:
            return config.GESTURE_NONE, 0.0

        self._last_fired_time = now
        self._history.clear()
        return label, confidence

    def history_points(self):
        """Recent (x, y) palm-center positions, for drawing a debug trail."""
        return [(x, y) for _, x, y in self._history]

    def _classify_delta(self, dx, dy):
        abs_dx = abs(dx)
        abs_dy = abs(dy)

        if abs_dx >= self.min_displacement and abs_dy <= self.max_cross_axis_drift:
            confidence = min(1.0, abs_dx / (self.min_displacement * 1.8))
            return (
                config.GESTURE_SWIPE_RIGHT if dx > 0 else config.GESTURE_SWIPE_LEFT,
                confidence,
            )

        if abs_dy >= self.min_displacement and abs_dx <= self.max_cross_axis_drift:
            confidence = min(1.0, abs_dy / (self.min_displacement * 1.8))
            return (
                config.GESTURE_SLIDE_DOWN if dy > 0 else config.GESTURE_SLIDE_UP,
                confidence,
            )

        return config.GESTURE_NONE, 0.0

    def reset(self):
        self._history.clear()
        self._last_fired_time = 0.0
