"""
calibration_engine: short onboarding check run before play starts. Verifies
hand visibility and lighting are good enough for stable recognition, rather
than deferring that discovery to mid-gameplay frustration. This is a
must-have in the MVP per the proposal, not a phase-2 nice-to-have.
"""
import time
from dataclasses import dataclass

import cv2
import numpy as np

import config


@dataclass
class CalibrationResult:
    passed: bool
    hand_visible_ratio: float
    mean_brightness: float
    frames_checked: int
    message: str


class CalibrationEngine:
    def __init__(self, duration_seconds=config.CALIBRATION_DURATION_SECONDS):
        self.duration_seconds = duration_seconds

    def run(self, camera_service, hand_tracker, frame_callback=None):
        """
        Runs a live calibration loop. `frame_callback(frame, elapsed, total)`
        is invoked each frame so the caller can render calibration UI; if it
        returns False, calibration is aborted early (e.g. user pressed Esc).
        Returns a CalibrationResult.
        """
        start = time.time()
        frames_checked = 0
        hand_visible_frames = 0
        brightness_samples = []

        while time.time() - start < self.duration_seconds:
            frame, _ = camera_service.read_frame()
            if frame is None:
                continue

            frames_checked += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness_samples.append(float(np.mean(gray)))

            hands_landmarks, results = hand_tracker.process(frame)
            if hands_landmarks:
                hand_visible_frames += 1
                frame = hand_tracker.draw_landmarks(frame, results)

            elapsed = time.time() - start
            if frame_callback is not None:
                keep_going = frame_callback(frame, elapsed, self.duration_seconds)
                if keep_going is False:
                    break

        if frames_checked == 0:
            return CalibrationResult(False, 0.0, 0.0, 0, "No frames captured from camera.")

        hand_ratio = hand_visible_frames / frames_checked
        mean_brightness = sum(brightness_samples) / len(brightness_samples)

        issues = []
        if hand_ratio < config.CALIBRATION_MIN_HAND_VISIBLE_RATIO:
            issues.append(
                f"Hand only visible {hand_ratio:.0%} of the time — "
                "move closer to the camera and keep your hand in frame."
            )
        if mean_brightness < config.CALIBRATION_MIN_BRIGHTNESS:
            issues.append("Room looks too dark — add more light for reliable tracking.")
        elif mean_brightness > config.CALIBRATION_MAX_BRIGHTNESS:
            issues.append("Frame is overexposed — reduce direct light or backlight.")

        passed = len(issues) == 0
        message = "Calibration passed." if passed else " ".join(issues)

        return CalibrationResult(
            passed=passed,
            hand_visible_ratio=hand_ratio,
            mean_brightness=mean_brightness,
            frames_checked=frames_checked,
            message=message,
        )
