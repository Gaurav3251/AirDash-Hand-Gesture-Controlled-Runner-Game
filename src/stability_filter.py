"""
stability_filter: the module that makes the system usable instead of
twitchy. A raw per-frame gesture prediction is noisy — this module only
lets a gesture "fire" as a command when it has been the majority prediction
across a rolling window AND exceeds a confidence floor AND isn't still in
cooldown from its last firing. This directly targets the false-trigger /
ambiguity problems called out in the proposal.
"""
import time
from collections import deque

import config


class StabilityFilter:
    def __init__(self,
                 window_size=config.STABILITY_WINDOW_SIZE,
                 min_agreement=config.STABILITY_MIN_AGREEMENT,
                 min_confidence=config.MIN_CONFIDENCE_THRESHOLD,
                 cooldown_seconds=config.COMMAND_COOLDOWN_SECONDS):
        self.window_size = window_size
        self.min_agreement = min_agreement
        self.min_confidence = min_confidence
        self.cooldown_seconds = cooldown_seconds

        self._history = deque(maxlen=window_size)
        self._last_fired_gesture = None
        self._last_fired_time = 0.0

    def update(self, gesture_label, confidence):
        """
        Feed one raw per-frame prediction in. Returns the gesture label to
        actually fire as a command, or None if nothing should fire this frame.
        """
        # Low-confidence frames don't even enter the voting window — they're
        # treated as noise, matching the "confidence exceeds threshold"
        # requirement from the must-have feature list.
        if confidence < self.min_confidence:
            self._history.append(config.GESTURE_NONE)
        else:
            self._history.append(gesture_label)

        if len(self._history) < self.window_size:
            return None  # not enough history yet to make a stable call

        majority_label, agreement = self._majority_vote()
        if majority_label == config.GESTURE_NONE or agreement < self.min_agreement:
            return None

        now = time.time()
        same_gesture_in_cooldown = (
            majority_label == self._last_fired_gesture
            and (now - self._last_fired_time) < self.cooldown_seconds
        )
        if same_gesture_in_cooldown:
            return None

        self._last_fired_gesture = majority_label
        self._last_fired_time = now
        return majority_label

    def _majority_vote(self):
        counts = {}
        for label in self._history:
            counts[label] = counts.get(label, 0) + 1
        majority_label = max(counts, key=counts.get)
        agreement = counts[majority_label] / len(self._history)
        return majority_label, agreement

    def reset(self):
        self._history.clear()
        self._last_fired_gesture = None
        self._last_fired_time = 0.0
