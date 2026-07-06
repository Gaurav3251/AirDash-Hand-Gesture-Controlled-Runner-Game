"""
camera_service: webcam initialization, frame capture, frame rate control.
Responsibility is intentionally narrow — this module knows nothing about
hands, gestures, or the game. It just hands back frames and timing info.
"""
import time
import cv2

import config


class CameraService:
    def __init__(self, camera_index=config.CAMERA_INDEX,
                 width=config.FRAME_WIDTH, height=config.FRAME_HEIGHT,
                 target_fps=config.TARGET_FPS):
        self.capture = cv2.VideoCapture(camera_index)
        if not self.capture.isOpened():
            raise RuntimeError(
                f"Could not open camera at index {camera_index}. "
                "Check that a webcam is connected and not in use by another app."
            )
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.target_frame_interval = 1.0 / target_fps
        self._last_frame_time = time.time()
        self._fps_samples = []

    def read_frame(self):
        """Returns (frame, actual_fps) or (None, 0) if the read failed."""
        ok, frame = self.capture.read()
        if not ok:
            return None, 0.0

        now = time.time()
        elapsed = now - self._last_frame_time
        self._last_frame_time = now
        fps = 1.0 / elapsed if elapsed > 0 else 0.0
        self._fps_samples.append(fps)
        if len(self._fps_samples) > 30:
            self._fps_samples.pop(0)

        frame = cv2.flip(frame, 1)  # mirror for natural user-facing control
        return frame, fps

    def average_fps(self):
        if not self._fps_samples:
            return 0.0
        return sum(self._fps_samples) / len(self._fps_samples)

    def release(self):
        self.capture.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
