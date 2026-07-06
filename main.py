"""
main.py: entry point. Wires camera -> hand_tracker -> feature_extractor ->
gesture_classifier -> stability_filter -> game_controller -> game_app, with
session_logger recording every stage. This file is intentionally the only
place that knows about the *order* of the pipeline — every module it calls
is independently testable and swappable.

Usage:
    python main.py --input keyboard
    python main.py --input gesture
    python main.py --input gesture --skip-calibration
"""
import argparse
import time

import pygame

import config
from src.camera_service import CameraService
from src.hand_tracker import HandTracker
from src.feature_extractor import extract_features
from src.gesture_classifier import classify
from src.motion_gesture_detector import MotionGestureDetector
from src.stability_filter import StabilityFilter
from src.calibration_engine import CalibrationEngine
from src.game_controller import GameController
from src.session_logger import SessionLogger
from src.ui_overlay import (
    draw_gesture_overlay, draw_calibration_overlay, draw_motion_trail, frame_to_pygame_surface,
)
from game.game_app import GameApp


def parse_args():
    parser = argparse.ArgumentParser(description="Gesture Gaming MVP")
    parser.add_argument("--input", choices=["keyboard", "gesture"], default="gesture",
                         help="Input source for the game.")
    parser.add_argument("--skip-calibration", action="store_true",
                         help="Skip the pre-game calibration step (dev iteration only).")
    return parser.parse_args()


def run_keyboard_mode(logger: SessionLogger):
    game = GameApp()
    controller = GameController()
    logger.start_session(input_mode="keyboard")

    while game.running:
        # Discrete key presses map to discrete actions (one lane change per
        # press, not per frame) — held-key repeat is handled by the OS/pygame
        # key-repeat setting if enabled, not by polling key state every frame.
        action = None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                game.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    game.running = False
                else:
                    action = controller.keyboard_to_action(event.key)

        if not game.running:
            break

        game.apply_action(action)
        game.update()
        game.draw()
        pygame.display.flip()
        logger.log_event(action_fired=action, fps=game.clock.get_fps())
        game.tick()

    logger.end_session(completed=game.game_over, final_score=game.score)
    game.quit()


def run_gesture_mode(logger: SessionLogger, skip_calibration: bool):
    camera = CameraService()
    tracker = HandTracker()
    stability_filter = StabilityFilter()
    motion_detector = MotionGestureDetector()
    controller = GameController()

    game = GameApp()

    if not skip_calibration:
        calibrator = CalibrationEngine()

        def calibration_frame_cb(frame, elapsed, total):
            game.handle_pygame_events()
            draw_calibration_overlay(frame, elapsed, total)
            surface = frame_to_pygame_surface(
                frame, target_size=(config.GAME_WINDOW_WIDTH, config.GAME_WINDOW_HEIGHT)
            )
            game.screen.blit(surface, (0, 0))
            pygame.display.flip()
            return game.running

        result = calibrator.run(camera, tracker, frame_callback=calibration_frame_cb)
        print(f"[calibration] passed={result.passed} "
              f"hand_visible={result.hand_visible_ratio:.0%} "
              f"brightness={result.mean_brightness:.0f} — {result.message}")
        if not result.passed:
            print("[calibration] Continuing anyway — adjust lighting/position for best results.")

    logger.start_session(input_mode="gesture")

    while game.running:
        loop_start = time.time()
        if not game.handle_pygame_events():
            break

        frame, fps = camera.read_frame()
        gesture_label, confidence, action = config.GESTURE_NONE, 0.0, None

        if frame is not None:
            hands_landmarks, results = tracker.process(frame)
            if hands_landmarks:
                features = extract_features(hands_landmarks[0])
                gesture_label, confidence = classify(features)
                motion_label, motion_confidence = motion_detector.update(features)
                if motion_label != config.GESTURE_NONE:
                    gesture_label, confidence = motion_label, motion_confidence
                frame = tracker.draw_landmarks(frame, results)

            # Draws the recent palm-path even on frames with no hand detected
            # this tick, so the trail doesn't visibly "jump" — it just uses
            # whatever history the detector currently has.
            draw_motion_trail(frame, motion_detector.history_points())

            if gesture_label in {
                config.GESTURE_SWIPE_LEFT,
                config.GESTURE_SWIPE_RIGHT,
                config.GESTURE_SLIDE_UP,
                config.GESTURE_SLIDE_DOWN,
            }:
                fired_gesture = gesture_label
                print(f"[gesture] {fired_gesture} fired (confidence={confidence:.2f})")
            else:
                fired_gesture = stability_filter.update(gesture_label, confidence)
                if fired_gesture:
                    print(f"[gesture] {fired_gesture} fired (confidence={confidence:.2f})")
            if fired_gesture:
                action = controller.gesture_to_action(fired_gesture)

            draw_gesture_overlay(frame, gesture_label, confidence, fps=fps)
            pip_surface = frame_to_pygame_surface(frame)
        else:
            pip_surface = None

        game.apply_action(action)
        game.update()
        game.draw(overlay_surface=pip_surface, overlay_caption="camera")
        pygame.display.flip()

        latency_ms = (time.time() - loop_start) * 1000
        logger.log_event(
            predicted_gesture=gesture_label,
            confidence=confidence,
            action_fired=action,
            fps=fps,
            latency_ms=latency_ms,
        )
        game.tick()

    logger.end_session(completed=game.game_over, final_score=game.score)
    camera.release()
    tracker.close()
    game.quit()


def main():
    args = parse_args()
    logger = SessionLogger()

    if args.input == "keyboard":
        run_keyboard_mode(logger)
    else:
        run_gesture_mode(logger, skip_calibration=args.skip_calibration)


if __name__ == "__main__":
    main()
