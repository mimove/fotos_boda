"""Local YuNet face detection and SFace embedding comparisons."""
import os
from functools import lru_cache
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

MODEL_DIR = Path(os.environ.get('FACE_MODEL_DIR', Path(__file__).resolve().parent / 'models'))
INDEX_MODEL = 'yunet-2023mar-sface-2021dec-v1'
INDEX_NAME = 'faces-sface.json'
SIMILARITY_THRESHOLD = 0.50


@lru_cache(maxsize=1)
def _models():
    cv2.setNumThreads(1)
    detector_path = MODEL_DIR / 'face_detection_yunet_2023mar.onnx'
    recognizer_path = MODEL_DIR / 'face_recognition_sface_2021dec.onnx'
    if not detector_path.is_file() or not recognizer_path.is_file():
        raise FileNotFoundError('Face recognition models are not installed')
    detector = cv2.FaceDetectorYN.create(str(detector_path), '', (320, 320), .9, .3, 5000)
    recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), '')
    return detector, recognizer


_model_lock = Lock()


def face_embeddings(image):
    """Return one SFace vector per detected face in a PIL RGB image."""
    image = np.asarray(image)
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    with _model_lock:
        detector, recognizer = _models()
        detector.setInputSize((bgr.shape[1], bgr.shape[0]))
        _, faces = detector.detect(bgr)
        if faces is None:
            return []
        return [recognizer.feature(recognizer.alignCrop(bgr, face)).flatten() for face in faces]


def cosine_matches(reference, encodings, threshold=SIMILARITY_THRESHOLD):
    reference = np.asarray(reference, dtype=np.float32)
    length = np.linalg.norm(reference)
    if not np.isfinite(length) or length == 0:
        raise ValueError('Invalid reference vector')
    for vector in encodings:
        vector = np.asarray(vector, dtype=np.float32)
        vector_length = np.linalg.norm(vector)
        if vector.shape != reference.shape or not np.isfinite(vector_length) or vector_length == 0:
            continue
        if np.dot(reference, vector) / (length * vector_length) >= threshold:
            return True
    return False
