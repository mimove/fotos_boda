import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app


class GuestAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data_patch = patch.object(app, 'DATA', Path(self.temp.name))
        self.data_patch.start()
        self.config_patch = patch.dict(app.app.config, {'GUEST_PASSWORD': 'abcTest12345', 'SESSION_COOKIE_SECURE': True})
        self.config_patch.start()
        self.client = app.app.test_client()

    def tearDown(self):
        self.config_patch.stop()
        self.data_patch.stop()
        self.temp.cleanup()

    def test_all_photo_and_static_routes_require_login(self):
        for path in ('/', '/galeria', '/api/gallery', '/photo/example', '/static/cover.jpg'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertIn('/login', response.headers['Location'])
            self.assertIn('no-store', response.headers['Cache-Control'])

    def test_correct_password_grants_access_with_secure_cookie(self):
        response = self.client.post('/login', data={'password': 'abcTest12345', 'next': '/galeria'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/galeria')
        self.assertIn('Secure', response.headers['Set-Cookie'])
        self.assertIn('HttpOnly', response.headers['Set-Cookie'])
        self.assertIn('no-store', self.client.get('/galeria').headers['Cache-Control'])

    def test_wrong_password_and_unsafe_redirect(self):
        self.assertEqual(self.client.post('/login', data={'password': 'incorrect'}).status_code, 401)
        response = self.client.post('/login', data={'password': 'abcTest12345', 'next': '//evil.example/'})
        self.assertEqual(response.headers['Location'], '/')
        response = self.client.post('/login', data={'password': 'abcTest12345', 'next': '/%2f%2fevil.example/'})
        self.assertEqual(response.headers['Location'], '/')

    def test_changing_password_invalidates_existing_session(self):
        self.client.post('/login', data={'password': 'abcTest12345'})
        self.assertEqual(self.client.get('/').status_code, 200)
        app.app.config['GUEST_PASSWORD'] = 'new-password'
        self.assertEqual(self.client.get('/').status_code, 302)

    def test_repeated_wrong_passwords_are_rate_limited(self):
        for _ in range(10):
            self.assertEqual(self.client.post('/login', data={'password': 'wrong'}).status_code, 401)
        self.assertEqual(self.client.post('/login', data={'password': 'wrong'}).status_code, 429)

    def test_missing_password_fails_closed(self):
        app.app.config['GUEST_PASSWORD'] = ''
        self.assertEqual(self.client.get('/').status_code, 503)
        self.assertEqual(self.client.get('/login').status_code, 503)


if __name__ == '__main__':
    unittest.main()
