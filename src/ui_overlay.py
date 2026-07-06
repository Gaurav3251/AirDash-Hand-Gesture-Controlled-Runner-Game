"""
ui_overlay: draws the on-screen gesture name, confidence bar, and
calibration warnings onto the camera frame, then converts that frame into a
pygame Surface so game_app can blit it as a picture-in-picture element.
Keeping this separate from game_app means the overlay logic doesn't care
whether it ends up in a pygame window, a cv2 debug window, or a test.
"""
import cv2
import numpy as np
import pygame

import config


def draw_gesture_overlay(frame_bgr, gesture_label, confidence, fps=None):
    """Draws gesture name + confidence bar directly onto frame_bgr (in place)."""
    h, w = frame_bgr.shape[:2]

    label_text = gesture_label if gesture_label else "none"
    cv2.putText(frame_bgr, label_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                config.OVERLAY_FONT_SCALE, (255, 255, 255), 2, cv2.LINE_AA)

    bar_x, bar_y, bar_w, bar_h = 10, 40, w - 20, 14
    cv2.rectangle(frame_bgr, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (80, 80, 80), 1)
    fill_w = int(bar_w * max(0.0, min(1.0, confidence or 0.0)))
    bar_color = (0, 200, 0) if (confidence or 0) >= config.MIN_CONFIDENCE_THRESHOLD else (0, 140, 255)
    cv2.rectangle(frame_bgr, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), bar_color, -1)

    if fps is not None:
        cv2.putText(frame_bgr, f"{fps:.0f} fps", (w - 80, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

    return frame_bgr


def draw_calibration_overlay(frame_bgr, elapsed, total, message=None):
    h, w = frame_bgr.shape[:2]
    progress = min(elapsed / total, 1.0)
    cv2.putText(frame_bgr, "Calibrating... hold hand in frame", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    bar_w = w - 20
    fill_w = int(bar_w * progress)
    cv2.rectangle(frame_bgr, (10, 40), (10 + bar_w, 54), (80, 80, 80), 1)
    cv2.rectangle(frame_bgr, (10, 40), (10 + fill_w, 54), (0, 180, 255), -1)
    if message:
        cv2.putText(frame_bgr, message, (10, h - 15), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return frame_bgr


def draw_motion_trail(frame_bgr, points):
    """
    Draws a line connecting recent palm-center positions (from
    MotionGestureDetector.history_points()) so you can see, in real time,
    what the swipe/slide detector is tracking — useful for calibrating how
    far/fast you need to move your hand.
    `points` is a list of (x, y) in normalized [0,1] coordinates.
    """
    h, w = frame_bgr.shape[:2]
    if len(points) < 2:
        return frame_bgr

    pixel_points = [(int(x * w), int(y * h)) for x, y in points]
    for i in range(1, len(pixel_points)):
        # Fade from dim to bright so the direction of travel is visible.
        brightness = int(80 + 175 * (i / len(pixel_points)))
        cv2.line(frame_bgr, pixel_points[i - 1], pixel_points[i], (0, brightness, 255), 2)

    cv2.circle(frame_bgr, pixel_points[-1], 6, (0, 255, 255), -1)
    return frame_bgr


def frame_to_pygame_surface(frame_bgr, target_size=None):
    """Converts a BGR OpenCV frame into a pygame Surface, resized for PiP display."""
    target_size = target_size or (config.OVERLAY_PIP_WIDTH, config.OVERLAY_PIP_HEIGHT)
    resized = cv2.resize(frame_bgr, target_size)
    frame_rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    # cv2 arrays are (H, W, 3); pygame.surfarray.make_surface expects (W, H, 3).
    surface = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
    return surface
