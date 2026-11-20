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
                {'id': 'near', 'encodings': [[0.59] + [0.0] * 127]},
                {'id': 'far', 'encodings': [[0.61] + [0.0] * 127]},
            ]
            (Path(directory) / 'faces.json').write_text(json.dumps(index))
            fake_face = types.SimpleNamespace(
                face_encodings=lambda image: [np.zeros(128)],
                face_distance=lambda encodings, face: np.linalg.norm(encodings - face, axis=1),
            )
            available = {'near': Path('/photos/Todos_Color/Ana y Miguel.0130.JPG'),
                         'far': Path('/photos/Todos_Color/Ana y Miguel.0131.JPG')}
            with patch.object(app, 'DATA', Path(directory)), patch.dict(app.app.config, {'GUEST_PASSWORD': 'testpassword'}), \
                    patch.dict(sys.modules, {'face_recognition': fake_face}), patch.object(app, 'photos', return_value=available), \
                    patch.object(app, 'selected', return_value=['near', 'far']), patch.object(app, 'items', side_effect=lambda ids: ids):
                client = app.app.test_client()
                with client.session_transaction() as session:
                    session['guest_auth'] = app.guest_token('testpassword')
                image = io.BytesIO()
                Image.new('RGB', (10, 10)).save(image, 'JPEG')
                image.seek(0)
                response = client.post('/api/match', data={'selfie': (image, 'selfie.jpg')})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json(), ['near'])

    def test_face_search_contains_only_current_gallery_selection(self):
        available = {
            'color_before': Path('/photos/Todos_Color/Ana y Miguel.0047.JPG'),
            'color_start': Path('/photos/Todos_Color/Ana y Miguel.0048.JPG'),
            'color_end': Path('/photos/Todos_Color/Ana y Miguel.0129.JPG'),
            'color_after': Path('/photos/Todos_Color/Ana y Miguel.0130.JPG'),
            'bw_before': Path('/photos/Todos_BN/Ana y Miguel.0036.JPG'),
            'bw_start': Path('/photos/Todos_BN/Ana y Miguel.0037.JPG'),
            'bw_end': Path('/photos/Todos_BN/Ana y Miguel.0104.JPG'),
            'bw_after': Path('/photos/Todos_BN/Ana y Miguel.0105.JPG'),
            'album': Path('/photos/Album/Ana y Miguel.0001.JPG'),
            'unselected': Path('/photos/Todos_Color/Ana y Miguel.0234.JPG'),
        }
        chosen = [key for key in available if key != 'unselected'] + ['missing']
        fake_face = types.SimpleNamespace(face_encodings=lambda image: [np.zeros(128)],
                                          face_distance=lambda encodings, face: np.linalg.norm(encodings - face, axis=1))
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / 'faces.json').write_text(json.dumps([
                {'id': key, 'encodings': [[0.0] * 128]} for key in available
            ]))
            (directory / 'selected.json').write_text(json.dumps(chosen))
            with patch.object(app, 'DATA', directory), patch.dict(app.app.config, {'GUEST_PASSWORD': 'testpassword'}), \
                    patch.dict(sys.modules, {'face_recognition': fake_face}), patch.object(app, 'photos', return_value=available):
                client = app.app.test_client()
                with client.session_transaction() as session:
                    session['guest_auth'] = app.guest_token('testpassword')

                def matching_ids():
                    image = io.BytesIO()
                    Image.new('RGB', (10, 10)).save(image, 'JPEG')
                    image.seek(0)
                    response = client.post('/api/match', data={'selfie': (image, 'selfie.jpg')})
                    self.assertEqual(response.status_code, 200)
                    return {item['id'] for item in response.get_json()}

                expected = {'color_before', 'color_after', 'bw_before', 'bw_after'}
                self.assertEqual({item['id'] for item in client.get('/api/gallery').get_json()}, expected)
                self.assertEqual(matching_ids(), expected)
                (directory / 'selected.json').write_text(json.dumps([key for key in chosen if key != 'color_before']))
                expected.remove('color_before')
                self.assertEqual({item['id'] for item in client.get('/api/gallery').get_json()}, expected)
                self.assertEqual(matching_ids(), expected)


if __name__ == '__main__':
    unittest.main()
