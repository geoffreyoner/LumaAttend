"""
Face detection + recognition using OpenCV DNN (YuNet + SFace).
No onnxruntime/dlib dependency - uses cv2.FaceDetectorYN and cv2.FaceRecognizerSF.
"""

import base64
import binascii
import json
import io
import os
import urllib.request
import numpy as np
import cv2
from config import Config

_yunet = None
_sface = None
_models_ready = False
_last_error = ""

def _download_model(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return True
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        print(f"[FaceEngine] Downloading {os.path.basename(path)} ...")
        temporary = path + ".download"
        try:
            with urllib.request.urlopen(url, timeout=30) as response, open(temporary, "wb") as output:
                total = 0
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > 120 * 1024 * 1024:
                        raise ValueError("Model download exceeds 120 MB limit")
                    output.write(chunk)
            if total < 1000:
                raise ValueError("Downloaded model is unexpectedly small")
            os.replace(temporary, path)
            return True
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)
    except Exception as e:
        print(f"[FaceEngine] Download failed: {e}")
        return False

def init_engine():
    global _yunet, _sface, _models_ready, _last_error
    if _models_ready:
        return True
    try:
        yunet_path = str(Config.MODEL_DIR / "face_detection_yunet_2023mar.onnx")
        sface_path = str(Config.MODEL_DIR / "face_recognition_sface_2021dec.onnx")
        ok1 = _download_model(Config.YUNET_MODEL_URL, yunet_path)
        ok2 = _download_model(Config.SFACE_MODEL_URL, sface_path)
        if not (ok1 and ok2):
            _last_error = "Model download failed. Check internet connection."
            return False
        _yunet = cv2.FaceDetectorYN.create(yunet_path, "", (320, 320), 0.7, 0.3, 5000)
        _sface = cv2.FaceRecognizerSF.create(sface_path, "")
        _models_ready = True
        return True
    except Exception as e:
        _last_error = f"Engine init error: {e}"
        return False

def decode_image(b64_string):
    """Decode base64 (with or without data:image prefix) to BGR numpy array."""
    if not isinstance(b64_string, str) or not b64_string.strip():
        return None
    if "," in b64_string:
        prefix, b64_string = b64_string.split(",", 1)
        if not prefix.lower().startswith("data:image/"):
            return None
    # Base64 string itself is bounded to avoid oversized allocation.
    if len(b64_string) > 7 * 1024 * 1024:
        return None
    try:
        raw = base64.b64decode(b64_string, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not raw or len(raw) > 5 * 1024 * 1024:
        return None
    arr = np.frombuffer(raw, dtype=np.uint8)
    try:
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except cv2.error:
        return None
    if img is None or img.ndim != 3 or img.shape[0] < 32 or img.shape[1] < 32:
        return None
    # Bound decoded dimensions before expensive DNN processing.
    if img.shape[0] * img.shape[1] > 16_000_000:
        return None
    return img

def detect_faces(img):
    """Returns detected face records; invalid image input is rejected safely."""
    if img is None or not hasattr(img, "shape") or len(img.shape) < 2:
        return []
    if not init_engine():
        return []
    h, w = img.shape[:2]
    _yunet.setInputSize((w, h))
    _, faces = _yunet.detect(img)
    if faces is None:
        return []
    return faces

def get_embedding(img):
    """Detect exactly one face, return (embedding_array, face_info) or (None, error_str)."""
    if not init_engine():
        return None, _last_error or "Engine not ready"
    faces = detect_faces(img)
    if len(faces) == 0:
        return None, "No face detected"
    if len(faces) > 1:
        return None, f"Multiple faces ({len(faces)})"
    face = faces[0]
    aligned = _sface.alignCrop(img, face)
    embedding = _sface.feature(aligned)
    embedding = embedding.flatten().astype(np.float32)
    # Normalize for cosine similarity
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    return embedding, None

def embedding_to_json(emb):
    """Serialize a numpy embedding to a JSON string for SQLite storage."""
    import numpy as _np
    if isinstance(emb, _np.ndarray):
        emb = emb.flatten().tolist()
    elif isinstance(emb, (list, tuple)):
        emb = list(emb)
    else:
        raise TypeError(f"Unsupported embedding type: {type(emb).__name__}")
    return json.dumps(emb)

def embedding_from_json(data):
    """Deserialize a JSON string (or list) back to a numpy float32 array."""
    import numpy as _np
    if data is None:
        return None
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    if isinstance(data, str):
        data = json.loads(data)
    arr = _np.array(data, dtype=_np.float32)
    # L2-normalize for cosine similarity
    n = _np.linalg.norm(arr)
    if n > 0:
        arr = arr / n
    return arr

def cosine_similarity(a, b):
    """Both vectors must be L2-normalized."""
    return float(np.dot(a, b))

def verify_face(img, stored_embedding_json, threshold=None):
    """
    Returns (matched_bool, similarity, message, user_embedding).
    Does NOT identify which user - caller does DB lookup.
    """
    if threshold is None:
        threshold = Config.FACE_MATCH_THRESHOLD
    emb, err = get_embedding(img)
    if emb is None:
        return False, 0.0, err, None
    if stored_embedding_json is None:
        return False, 0.0, "No stored template", emb
    stored = embedding_from_json(stored_embedding_json)
    sim = cosine_similarity(emb, stored)
    matched = sim >= threshold
    return matched, sim, ("Match" if matched else "Below threshold"), emb

def identify_face(img, all_users_with_embeddings, threshold=None):
    """
    Find best matching user from list of (user_id, embedding_json).
    Returns (user_id, similarity, message).
    """
    if threshold is None:
        threshold = Config.FACE_MATCH_THRESHOLD
    emb, err = get_embedding(img)
    if emb is None:
        return None, 0.0, err
    best_id = None
    best_sim = -1.0
    for uid, emb_json in all_users_with_embeddings:
        if not emb_json:
            continue
        try:
            stored = embedding_from_json(emb_json)
            if stored is None or stored.shape != emb.shape or not np.all(np.isfinite(stored)):
                continue
            sim = cosine_similarity(emb, stored)
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
        if not np.isfinite(sim):
            continue
        if sim > best_sim:
            best_sim = sim
            best_id = uid
    if best_sim >= threshold and best_id is not None:
        return best_id, best_sim, "Identified"
    return None, best_sim, "No match above threshold"