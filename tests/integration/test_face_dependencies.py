"""Check the production recognition dependencies are importable."""
import cv2
import numpy as np


def test_opencv_face_recognition_api_available():
    assert hasattr(cv2, 'FaceDetectorYN')
    assert hasattr(cv2, 'FaceRecognizerSF')
    assert np.isfinite(np.array([1.0])).all()
