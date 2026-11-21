import pytest


def test_tile_inference_uses_overlapping_crops_and_extracts_features():
    np = pytest.importorskip('numpy')
    pytest.importorskip('cv2')
    from evaluation.tile_faces import extract_tile_vectors

    class Detector:
        def __init__(self):
            self.sizes = []
        def setInputSize(self, size):
            self.sizes.append(size)
        def detect(self, image):
            return 1, np.array([[0, 0, 4, 4] + [0] * 11], dtype=np.float32)

    class Recognizer:
        def alignCrop(self, image, face):
            return image[:4, :4]
        def feature(self, image):
            return np.array([[float(image.mean()), 1.]])

    detector = Detector()
    image = np.full((100, 80, 3), 127, dtype=np.uint8)
    result = extract_tile_vectors(image, detector, Recognizer())
    assert len(result) == 4
    assert len(detector.sizes) == 4
    assert all(vector.shape == (2,) for vector in result)


def test_real_yunet_and_sface_accept_blank_image_when_models_available():
    import os
    np = pytest.importorskip('numpy')
    cv2 = pytest.importorskip('cv2')
    from evaluation.tile_faces import extract_tile_vectors
    detector_path = os.environ.get('EVAL_YUNET_MODEL')
    recognizer_path = os.environ.get('EVAL_SFACE_MODEL')
    if not detector_path or not recognizer_path:
        pytest.skip('Set EVAL_YUNET_MODEL and EVAL_SFACE_MODEL to run model smoke test')
    detector = cv2.FaceDetectorYN.create(detector_path, '', (320, 320), .9, .3, 5000)
    recognizer = cv2.FaceRecognizerSF.create(recognizer_path, '')
    assert extract_tile_vectors(np.zeros((320, 320, 3), dtype=np.uint8), detector, recognizer) == []


def test_real_models_extract_reference_face_when_fixture_available():
    import os
    np = pytest.importorskip('numpy')
    cv2 = pytest.importorskip('cv2')
    from PIL import Image, ImageOps
    from evaluation.tile_faces import extract_tile_vectors
    detector_path = os.environ.get('EVAL_YUNET_MODEL')
    recognizer_path = os.environ.get('EVAL_SFACE_MODEL')
    photo_path = os.environ.get('EVAL_REFERENCE_PHOTO')
    if not detector_path or not recognizer_path or not photo_path:
        pytest.skip('Set model paths and EVAL_REFERENCE_PHOTO for real-face smoke test')
    detector = cv2.FaceDetectorYN.create(detector_path, '', (320, 320), .9, .3, 5000)
    recognizer = cv2.FaceRecognizerSF.create(recognizer_path, '')
    with Image.open(photo_path) as image:
        rgb = np.asarray(ImageOps.exif_transpose(image).convert('RGB'))
    features = extract_tile_vectors(rgb, detector, recognizer)
    assert features and all(np.isfinite(feature).all() for feature in features)
