"""Check the real face-recognition dependency loads with its model files."""
import subprocess
import sys


def test_face_recognition_and_model_files_are_available():
    subprocess.run(
        [sys.executable, '-c',
         'import os, face_recognition_models, face_recognition; '
         'assert os.path.isfile(face_recognition_models.face_recognition_model_location())'],
        check=True,
        capture_output=True,
        text=True,
    )
