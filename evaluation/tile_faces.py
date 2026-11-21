"""Experimental offline YuNet and SFace inference over overlapping crops."""
import cv2

from evaluation.face_eval import tile_boxes


def extract_tile_vectors(rgb, detector, recognizer, scale=1.6):
    """Return feature vectors for each detected crop; results may contain duplicates."""
    if scale <= 0:
        raise ValueError('Scale must be positive')
    height, width = rgb.shape[:2]
    vectors = []
    for left, top, right, bottom in tile_boxes(width, height):
        crop = rgb[top:bottom, left:right]
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        bgr = cv2.cvtColor(crop, cv2.COLOR_RGB2BGR)
        detector.setInputSize((bgr.shape[1], bgr.shape[0]))
        _, faces = detector.detect(bgr)
        if faces is not None:
            for face in faces:
                vectors.append(recognizer.feature(recognizer.alignCrop(bgr, face)).flatten())
    return vectors
