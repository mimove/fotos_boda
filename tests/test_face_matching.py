import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
import app


class FaceMatchingTests(unittest.TestCase):
    def test_matches_within_relaxed_distance_and_excludes_more_distant_faces(self):
        with tempfile.TemporaryDirectory() as directory:
            index = [
                {'id': 'near', 'encodings': [[0.64] + [0.0] * 127]},
                {'id': 'far', 'encodings': [[0.66] + [0.0] * 127]},
            ]
            (Path(directory) / 'faces.json').write_text(json.dumps(index))
            fake_face = types.SimpleNamespace(
                face_encodings=lambda image: [np.zeros(128)],
                face_distance=lambda encodings, face: np.linalg.norm(encodings - face, axis=1),
            )
            with patch.object(app, 'DATA', Path(directory)), patch.dict(app.app.config, {'GUEST_PASSWORD': 'testpassword'}), \
                    patch.dict(sys.modules, {'face_recognition': fake_face}), patch.object(app, 'items', side_effect=lambda ids: ids):
                client = app.app.test_client()
                with client.session_transaction() as session:
                    session['guest_auth'] = app.guest_token('testpassword')
                image = io.BytesIO()
                Image.new('RGB', (10, 10)).save(image, 'JPEG')
                image.seek(0)
                response = client.post('/api/match', data={'selfie': (image, 'selfie.jpg')})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json(), ['near'])


if __name__ == '__main__':
    unittest.main()
