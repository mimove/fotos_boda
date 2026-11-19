import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import app


class PhotoPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'one.jpg'
        Image.new('RGB', (800, 600), 'red').save(self.path)
        self.root_patch = patch.object(app, 'PHOTO_ROOT', self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_photo_list_is_reused_and_refreshes(self):
        with patch.object(app, '_scan_photo_paths', wraps=app._scan_photo_paths) as scan:
            with patch('app.time.monotonic', return_value=100):
                first = app.photos()
                self.assertEqual(app.photos(), first)
                self.assertEqual(scan.call_count, 1)
            Image.new('RGB', (10, 10), 'blue').save(self.root / 'two.jpg')
            with patch('app.time.monotonic', return_value=140):
                self.assertEqual(len(app.photos()), 2)
                self.assertEqual(scan.call_count, 2)

    def test_thumbnail_cache_invalidates_when_photo_changes(self):
        with patch.object(app, '_render_thumbnail', wraps=app._render_thumbnail) as render:
            first = app.thumbnail_bytes(self.path)
            self.assertEqual(app.thumbnail_bytes(self.path), first)
            self.assertEqual(render.call_count, 1)
            Image.new('RGB', (600, 800), 'blue').save(self.path)
            second = app.thumbnail_bytes(self.path)
            self.assertNotEqual(first, second)
            self.assertEqual(render.call_count, 2)

    def test_cached_thumbnails_are_private_and_require_login(self):
        photo_id = next(iter(app.photos()))
        url = app.signed_url(photo_id) + '&thumb=1'
        with patch.dict(app.app.config, {'GUEST_PASSWORD': 'testpassword'}):
            client = app.app.test_client()
            self.assertEqual(client.get(url).status_code, 302)
            with client.session_transaction() as session:
                session['guest_auth'] = app.guest_token('testpassword')
            for _ in range(2):
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn('no-store', response.headers['Cache-Control'])


if __name__ == '__main__':
    unittest.main()
