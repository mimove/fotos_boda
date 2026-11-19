import io
import sys
import types
import unittest
from unittest.mock import patch
from PIL import Image
import app


class UploadTests(unittest.TestCase):
    def setUp(self):
        config = patch.dict(app.app.config, {'GUEST_PASSWORD': 'testpassword'})
        config.start()
        self.addCleanup(config.stop)
        self.client = app.app.test_client()
        with self.client.session_transaction() as session:
            session['guest_auth'] = app.guest_token('testpassword')
        self.modules = {'face_recognition': types.SimpleNamespace(face_encodings=lambda image: []),
                        'numpy': types.SimpleNamespace(asarray=lambda image: image)}

    def send_image(self, fmt):
        data = io.BytesIO()
        Image.new('RGB', (10, 10)).save(data, format=fmt)
        data.seek(0)
        with patch.dict(sys.modules, self.modules):
            return self.client.post('/api/match', data={'selfie': (data, 'photo.jpg')})

    def test_rejects_unsupported_image_format(self):
        response = self.send_image('BMP')
        self.assertEqual(response.status_code, 400)
        self.assertIn('JPEG', response.get_json()['error'])

    def test_jpeg_reaches_face_detection(self):
        response = self.send_image('JPEG')
        self.assertIn('una sola cara', response.get_json()['error'])

    def test_rejects_excessive_image_dimensions(self):
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 50):
            response = self.send_image('JPEG')
        self.assertEqual(response.status_code, 400)
        self.assertIn('megapíxeles', response.get_json()['error'])

    def test_rejects_large_upload(self):
        response = self.client.post('/api/match', data={'selfie': (io.BytesIO(b'x' * (12 * 1024 * 1024)), 'photo.jpg')})
        self.assertEqual(response.status_code, 413)


if __name__ == '__main__':
    unittest.main()
