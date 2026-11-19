import io
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import piexif
from PIL import Image
import app


class PhotoDateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'wedding.jpg'
        raw = io.BytesIO()
        exif = piexif.dump({'0th': {piexif.ImageIFD.Orientation: 6}, 'Exif': {piexif.ExifIFD.DateTimeOriginal: '2025:11:29 14:00:00'}})
        Image.new('RGB', (12, 8), 'red').save(raw, 'JPEG', exif=exif)
        xmp = (b'http://ns.adobe.com/xap/1.0/\x00' + b'<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:CreateDate="2025-11-29T14:00:00+01:00"/>')
        segment = b'\xff\xe1' + (len(xmp) + 2).to_bytes(2, 'big') + xmp
        original = raw.getvalue()
        self.path.write_bytes(original[:2] + segment + original[2:])
        self.original = self.path.read_bytes()
        self.photo_patch = patch.object(app, 'photos', return_value={'abc': self.path})
        self.photo_patch.start()
        self.config_patch = patch.dict(app.app.config, {'GUEST_PASSWORD': 'testpassword'})
        self.config_patch.start()
        self.client = app.app.test_client()
        with self.client.session_transaction() as session:
            session['guest_auth'] = app.guest_token('testpassword')
        self.url = app.signed_url('abc')

    def tearDown(self):
        self.photo_patch.stop()
        self.config_patch.stop()
        self.temp.cleanup()

    def assert_current_copy(self, data):
        exif = piexif.load(data)
        today = datetime.now(timezone.utc).strftime('%Y:%m:%d')
        self.assertTrue(exif['Exif'][piexif.ExifIFD.DateTimeOriginal].decode().startswith(today))
        self.assertEqual(exif['0th'][piexif.ImageIFD.Orientation], 6)
        with Image.open(io.BytesIO(data)) as image:
            self.assertIn(datetime.now(timezone.utc).strftime('%Y-%m-%d'), image.info['xmp'].decode())
        self.assertEqual(data[data.index(b'\xff\xda'):], self.original[self.original.index(b'\xff\xda'):])
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_phone_copy_has_current_date_and_preserves_image_data(self):
        response = self.client.get(self.url + '&save=1&tz=0')
        self.assertEqual(response.status_code, 200)
        self.assert_current_copy(response.data)
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))

    def test_zip_copies_have_current_date(self):
        response = self.client.post('/download-all', data={'photos': json.dumps([self.url]), 'tz': '0'})
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as bundle:
            self.assert_current_copy(bundle.read(bundle.namelist()[0]))

    def test_bad_timezone_is_rejected(self):
        self.assertEqual(self.client.get(self.url + '&save=1&tz=9999').status_code, 400)

    def test_phone_timezone_is_recorded_in_exif(self):
        response = self.client.get(self.url + '&save=1&tz=-330')
        exif = piexif.load(response.data)
        self.assertEqual(exif['Exif'][piexif.ExifIFD.OffsetTimeOriginal], b'+05:30')


if __name__ == '__main__':
    unittest.main()
