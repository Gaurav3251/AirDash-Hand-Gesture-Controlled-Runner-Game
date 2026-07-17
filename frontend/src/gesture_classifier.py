import json
import math

def dist(a, b):
    return math.sqrt((a['x'] - b['x'])**2 + (a['y'] - b['y'])**2)

def extract_features(landmarks):
    if not landmarks or len(landmarks) == 0:
        return None

    wrist = landmarks[0]
    xs = [p['x'] for p in landmarks]
    ys = [p['y'] for p in landmarks]

    palm_center_x = sum(xs) / len(landmarks)
    palm_center_y = sum(ys) / len(landmarks)

    finger_tips = [4, 8, 12, 16, 20]
    finger_mcps = [2, 5, 9, 13, 17]

    wrist_to_middle_mcp = dist(wrist, landmarks[9])
    hand_scale = wrist_to_middle_mcp if wrist_to_middle_mcp > 0 else 1.0

    finger_extended = []

    # 1. Custom thumb extension check
    thumb_tip = landmarks[4]
    thumb_mcp = landmarks[2]
    index_mcp = landmarks[5]

    is_thumb_extended = (
        dist(thumb_tip, wrist) > dist(thumb_mcp, wrist) * 1.1 and
        dist(thumb_tip, index_mcp) / hand_scale > 0.45
    )
    finger_extended.append(is_thumb_extended)

    # 2. Other fingers (Index, Middle, Ring, Pinky)
    for i in range(1, 5):
        tip = landmarks[finger_tips[i]]
        mcp = landmarks[finger_mcps[i]]
        is_extended = dist(tip, wrist) > dist(mcp, wrist) * 1.15
        finger_extended.append(is_extended)

    extended_count = sum(1 for f in finger_extended if f)
    extension_ratio = extended_count / 5.0
    curl_ratio = 1.0 - extension_ratio

    return {
        "palmCenterX": palm_center_x,
        "palmCenterY": palm_center_y,
        "fingerExtended": finger_extended,
        "extensionRatio": extension_ratio,
        "curl_ratio": curl_ratio,
        "handScale": hand_scale
    }

def classify_static_gesture(features, landmarks):
    if not features or not landmarks:
        return {"label": "none", "confidence": 0.0}

    # Unpack finger extensions
    thumb, index, middle, ring, pinky = features["fingerExtended"]

    # 1. Pointing Up: index extended, other fingers curled.
    if index and not thumb and not middle and not ring and not pinky:
        return {"label": "pointing_up", "confidence": 0.95}

    # 2. Pinch / OK Sign (Duck): thumb tip (4) and index tip (8) touching, index finger is arched (not curled tightly).
    thumb_tip = landmarks[4]
    index_tip = landmarks[8]
    index_knuckle = landmarks[5]
    pinch_dist = dist(thumb_tip, index_tip) / features["handScale"]
    index_curl = dist(index_tip, index_knuckle) / features["handScale"]

    if pinch_dist < 0.22 and index_curl > 0.38:
        return {"label": "pinch", "confidence": max(0.0, 1.0 - pinch_dist)}

    # 3. Thumbs up: thumb extended, all others curled.
    if thumb and not index and not middle and not ring and not pinky:
        return {"label": "thumbs_up", "confidence": 0.9}

    # 4. Fist: all 4 fingers (index, middle, ring, pinky) are curled tightly.
    if not index and not middle and not ring and not pinky:
        return {"label": "fist", "confidence": 0.95}

    # 5. Peace sign: index and middle extended, thumb/ring/pinky curled.
    if not thumb and index and middle and not ring and not pinky:
        return {"label": "peace_sign", "confidence": 0.9}

    # 6. Open palm: at least 4 fingers extended.
    if features["extensionRatio"] >= 0.8:
        return {"label": "open_palm", "confidence": features["extensionRatio"]}

    return {"label": "none", "confidence": 0.0}

def classify_frame(landmarks_json):
    try:
        landmarks = json.loads(landmarks_json)
        features = extract_features(landmarks)
        if not features:
            return json.dumps({
                "label": "none",
                "confidence": 0.0,
                "palmCenterX": 0.5,
                "palmCenterY": 0.5,
                "handScale": 1.0
            })

        result = classify_static_gesture(features, landmarks)
        return json.dumps({
            "label": result["label"],
            "confidence": result["confidence"],
            "palmCenterX": features["palmCenterX"],
            "palmCenterY": features["palmCenterY"],
            "handScale": features["handScale"]
        })
    except Exception as e:
        return json.dumps({
            "label": "none",
            "confidence": 0.0,
            "error": str(e),
            "palmCenterX": 0.5,
            "palmCenterY": 0.5,
            "handScale": 1.0
        })
