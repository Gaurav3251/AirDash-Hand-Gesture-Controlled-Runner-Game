"""
feature_extractor: converts raw MediaPipe landmarks into a compact,
interpretable feature vector (finger extension states, palm center,
horizontal tilt, vertical position). gesture_classifier consumes this
instead of raw landmarks so classification rules stay readable.

MediaPipe hand landmark indices used:
  0  = wrist
  4  = thumb tip     2  = thumb MCP
  8  = index tip      5 = index MCP
  12 = middle tip      9 = middle MCP
  16 = ring tip        13 = ring MCP
  20 = pinky tip        17 = pinky MCP
"""
from dataclasses import dataclass, field

WRIST = 0
FINGER_TIPS = [4, 8, 12, 16, 20]
FINGER_MCPS = [2, 5, 9, 13, 17]  # base knuckle of each finger
FINGER_PIPS = [3, 6, 10, 14, 18]  # middle joint, used for curl comparison


@dataclass
class HandFeatures:
    palm_center_x: float
    palm_center_y: float
    wrist_y: float
    finger_extended: list = field(default_factory=list)  # 5 bools, thumb..pinky
    extension_ratio: float = 0.0    # fraction of fingers extended
    curl_ratio: float = 0.0         # fraction of fingers curled
    horizontal_spread: float = 0.0  # x-span of hand, used for tilt detection
    tilt: float = 0.0               # palm_center_x - wrist_x, sign gives direction
    pinch_distance: float = 1.0     # thumb tip to index tip distance


def extract_features(landmarks) -> HandFeatures:
    """
    landmarks: list of 21 (x, y, z) normalized tuples from hand_tracker.
    Returns a HandFeatures instance. Assumes landmarks is non-empty.
    """
    xs = [p[0] for p in landmarks]
    ys = [p[1] for p in landmarks]

    wrist_x, wrist_y = landmarks[WRIST][0], landmarks[WRIST][1]
    palm_center_x = sum(xs) / len(xs)
    palm_center_y = sum(ys) / len(ys)

    finger_extended = []
    for tip_idx, mcp_idx in zip(FINGER_TIPS, FINGER_MCPS):
        tip = landmarks[tip_idx]
        mcp = landmarks[mcp_idx]
        # Extended = tip is farther from the wrist than the MCP joint is.
        dist_tip = _dist(tip, landmarks[WRIST])
        dist_mcp = _dist(mcp, landmarks[WRIST])
        finger_extended.append(dist_tip > dist_mcp * 1.15)

    extension_ratio = sum(finger_extended) / len(finger_extended)
    curl_ratio = 1.0 - extension_ratio
    horizontal_spread = max(xs) - min(xs)
    tilt = palm_center_x - wrist_x
    pinch_distance = _dist(landmarks[4], landmarks[8])

    return HandFeatures(
        palm_center_x=palm_center_x,
        palm_center_y=palm_center_y,
        wrist_y=wrist_y,
        finger_extended=finger_extended,
        extension_ratio=extension_ratio,
        curl_ratio=curl_ratio,
        horizontal_spread=horizontal_spread,
        tilt=tilt,
        pinch_distance=pinch_distance,
    )


def _dist(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
