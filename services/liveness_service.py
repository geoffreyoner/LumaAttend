"""
Basic anti-spoofing using challenge-response (blink + head turn).
This is a BASIC layer - not foolproof against sophisticated attacks.
"""

import time
import random
import threading

_challenges = {}
_lock = threading.Lock()

CHALLENGE_TTL = 60  # seconds

CHALLENGE_TYPES = [
    {"type": "blink", "instruction": "Please blink your eyes", "duration": 5},
    {"type": "turn_left", "instruction": "Slowly turn your head LEFT", "duration": 5},
    {"type": "turn_right", "instruction": "Slowly turn your head RIGHT", "duration": 5},
]

def create_challenge(session_id):
    with _lock:
        challenge = random.choice(CHALLENGE_TYPES).copy()
        challenge["created_at"] = time.time()
        challenge["verified"] = False
        _challenges[session_id] = challenge
        return {
            "type": challenge["type"],
            "instruction": challenge["instruction"],
            "duration": challenge["duration"],
            "session_id": session_id,
        }

def verify_challenge(session_id, metrics):
    """
    metrics: dict from frontend e.g. {"blink_detected": True} or {"head_turn": "left"}
    This is a simplified verification - real liveness needs proper ML.
    """
    with _lock:
        ch = _challenges.get(session_id)
        if not ch:
            return False, "No active challenge"
        if time.time() - ch["created_at"] > CHALLENGE_TTL:
            del _challenges[session_id]
            return False, "Challenge expired"
        ctype = ch["type"]
        if ctype == "blink" and metrics.get("blink_detected"):
            ch["verified"] = True
        elif ctype == "turn_left" and metrics.get("head_direction") == "left":
            ch["verified"] = True
        elif ctype == "turn_right" and metrics.get("head_direction") == "right":
            ch["verified"] = True
        if ch["verified"]:
            del _challenges[session_id]
            return True, "Liveness verified"
        return False, "Challenge not satisfied"

def is_verified(session_id):
    with _lock:
        ch = _challenges.get(session_id)
        return ch is not None and ch.get("verified", False)