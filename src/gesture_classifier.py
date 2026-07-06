"""
gesture_classifier: rule-based classification for the MVP STATIC gesture
vocabulary (open_palm, fist, thumbs_up). Movement gestures (swipe/slide,
including jump/duck) are intentionally NOT handled here — they live in
motion_gesture_detector.py, which looks at motion across frames instead of
a single pose. Keeping static and dynamic gestures in separate modules
avoids the two rule sets fighting over ambiguous in-between frames.

Kept deliberately simple and swappable — a learned classifier can replace
this module later without changing anything downstream, as long as it
returns the same (label, confidence) shape.
"""
import config
from src.feature_extractor import HandFeatures


def classify(features: HandFeatures):
    """
    Returns (gesture_label, confidence) where confidence is in [0, 1].
    Priority order matters:
      1. Thumbs-up — distinct enough (only thumb extended) to check first.
      2. Fist — most fingers curled.
      3. Open palm — most fingers extended.
    Jump and duck are NOT static poses here — they fire only from motion
    (slide_up / slide_down in motion_gesture_detector.py), so a hand simply
    held up high does not trigger anything.
    """
    thumb, index, middle, ring, pinky = features.finger_extended

    # Thumbs-up: thumb extended, everything else curled.
    if thumb and not any([index, middle, ring, pinky]):
        return config.GESTURE_THUMBS_UP, 0.9

    # Fist: most fingers curled.
    if features.curl_ratio >= config.FIST_CURL_RATIO:
        confidence = min(1.0, features.curl_ratio)
        return config.GESTURE_FIST, confidence

    # Open palm: most fingers extended.
    if features.extension_ratio >= config.OPEN_PALM_EXTENSION_RATIO:
        confidence = min(1.0, features.extension_ratio)
        return config.GESTURE_OPEN_PALM, confidence

    return config.GESTURE_NONE, 0.0
