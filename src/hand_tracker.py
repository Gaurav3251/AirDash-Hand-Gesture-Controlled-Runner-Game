"""
hand_tracker: wraps MediaPipe Hands. Responsible only for turning a BGR
frame into landmark coordinates (and drawing them for the overlay). It does
not interpret what the landmarks mean — that's feature_extractor's job.
"""
import cv2
import mediapipe as mp

import config


class HandTracker:
    def __init__(self,
                 max_num_hands=config.MAX_NUM_HANDS,
                 min_detection_confidence=config.MIN_DETECTION_CONFIDENCE,
                 min_tracking_confidence=config.MIN_TRACKING_CONFIDENCE):
        self._mp_hands = mp.solutions.hands
        self._mp_drawing = mp.solutions.drawing_utils
        self._mp_styles = mp.solutions.drawing_styles
        self.hands = self._mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def process(self, frame_bgr):
        """
        Returns a list of landmark sets, one per detected hand. Each landmark
        set is a list of 21 (x, y, z) tuples in normalized [0,1] coordinates.
        Empty list means no hand detected.
        """
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False
        results = self.hands.process(frame_rgb)

        hands_landmarks = []
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                points = [(lm.x, lm.y, lm.z) for lm in hand_landmarks.landmark]
                hands_landmarks.append(points)
        return hands_landmarks, results

    def draw_landmarks(self, frame_bgr, results):
        """Draws the skeleton overlay in place on frame_bgr for visual feedback."""
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                self._mp_drawing.draw_landmarks(
                    frame_bgr,
                    hand_landmarks,
                    self._mp_hands.HAND_CONNECTIONS,
                    self._mp_styles.get_default_hand_landmarks_style(),
                    self._mp_styles.get_default_hand_connections_style(),
                )
        return frame_bgr

    def close(self):
        self.hands.close()
