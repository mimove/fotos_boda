import io
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image
import pytest
import app


def image_file(fmt='JPEG'):
    image = io.BytesIO()
    Image.new('RGB', (10, 10)).save(image, fmt)
    image.seek(0)
    return image


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(app, 'DATA', tmp_path)
    monkeypatch.setitem(app.app.config, 'GUEST_PASSWORD', 'testpassword')
    monkeypatch.setattr(app, 'face_embeddings', lambda image: [np.array([1., 0.])])
    client = app.app.test_client()
    with client.session_transaction() as session:
        session['guest_auth'] = app.guest_token('testpassword')
    return client


def test_upload_validation(client, monkeypatch):
    response = client.post('/api/match', data={'selfie': (image_file('BMP'), 'photo.jpg')})
    assert response.status_code == 400
    with patch.object(Image, 'MAX_IMAGE_PIXELS', 50):
        response = client.post('/api/match', data={'selfie': (image_file(), 'photo.jpg')})
    assert response.status_code == 400
    response = client.post('/api/match', data={'selfie': (io.BytesIO(b'x' * (12 * 1024 * 1024)), 'photo.jpg')})
    assert response.status_code == 413
    monkeypatch.setattr(app, 'face_embeddings', lambda image: [])
    response = client.post('/api/match', data={'selfie': (image_file(), 'photo.jpg')})
    assert response.status_code == 400
    assert 'una sola cara' in response.get_json()['error']
    monkeypatch.setattr(app, 'face_embeddings', lambda image: [np.ones(2), np.ones(2)])
    response = client.post('/api/match', data={'selfie': (image_file(), 'photo.jpg')})
    assert response.status_code == 400


def test_match_uses_cosine_and_current_gallery_selection(client, monkeypatch, tmp_path):
    available = {
        'match': Path('/photos/Todos_Color/Ana y Miguel.0130.JPG'),
        'distant': Path('/photos/Todos_Color/Ana y Miguel.0131.JPG'),
        'excluded': Path('/photos/Todos_Color/Ana y Miguel.0048.JPG'),
        'unselected': Path('/photos/Todos_Color/Ana y Miguel.0234.JPG'),
    }
    index = {'model': app.INDEX_MODEL, 'photos': [
        {'id': 'match', 'encodings': [[.6, .8]]},
        {'id': 'distant', 'encodings': [[.4, (1 - .4 ** 2) ** .5]]},
        {'id': 'excluded', 'encodings': [[1, 0]]},
        {'id': 'unselected', 'encodings': [[1, 0]]},
    ]}
    (tmp_path / app.INDEX_NAME).write_text(json.dumps(index))
    (tmp_path / 'selected.json').write_text(json.dumps(['match', 'distant', 'excluded']))
    monkeypatch.setattr(app, 'photos', lambda: available)
    response = client.post('/api/match', data={'selfie': (image_file(), 'photo.jpg')})
    assert response.status_code == 200
    assert [item['id'] for item in response.get_json()] == ['match']
    (tmp_path / 'selected.json').write_text(json.dumps(['distant']))
    response = client.post('/api/match', data={'selfie': (image_file(), 'photo.jpg')})
    assert response.get_json() == []


def test_missing_or_wrong_model_index_fails_closed(client, tmp_path):
    for content in [None, {'model': 'old-dlib', 'photos': []}]:
        if content is not None:
            (tmp_path / app.INDEX_NAME).write_text(json.dumps(content))
        response = client.post('/api/match', data={'selfie': (image_file(), 'photo.jpg')})
        assert response.status_code == 503


def test_real_model_end_to_end_when_reference_available(monkeypatch, tmp_path):
    import os
    import face_engine
    photo = os.environ.get('EVAL_REFERENCE_PHOTO')
    if not photo:
        pytest.skip('Set EVAL_REFERENCE_PHOTO for real face-search integration test')
    monkeypatch.setattr(app, 'DATA', tmp_path)
    monkeypatch.setitem(app.app.config, 'GUEST_PASSWORD', 'testpassword')
    monkeypatch.setattr(app, 'photos', lambda: {'photo': Path('/photos/Todos_Color/Ana y Miguel.0130.JPG')})
    with Image.open(photo) as source:
        reference = app.ImageOps.exif_transpose(source).convert('RGB')
    reference.thumbnail((1600, 1600))
    features = face_engine.face_embeddings(reference)
    assert len(features) == 1
    (tmp_path / app.INDEX_NAME).write_text(json.dumps({
        'model': app.INDEX_MODEL,
        'photos': [{'id': 'photo', 'encodings': [features[0].tolist()]}],
    }))
    (tmp_path / 'selected.json').write_text(json.dumps(['photo']))
    client = app.app.test_client()
    with client.session_transaction() as session:
        session['guest_auth'] = app.guest_token('testpassword')
    with open(photo, 'rb') as image:
        response = client.post('/api/match', data={'selfie': (image, 'photo.jpg')})
    assert response.status_code == 200
    assert [item['id'] for item in response.get_json()] == ['photo']


@pytest.mark.parametrize(('directory', 'number', 'allowed'), [
    ('Todos_Color', 47, True), ('Todos_Color', 48, False),
    ('Todos_Color', 129, False), ('Todos_Color', 130, True),
    ('Todos_BN', 36, True), ('Todos_BN', 37, False),
    ('Todos_BN', 104, False), ('Todos_BN', 105, True),
    ('Album', 130, False),
])
def test_gallery_exclusion_boundaries(directory, number, allowed):
    path = Path('/photos') / directory / f'Ana y Miguel.{number:04d}.JPG'
    assert bool(app.gallery_category(path)) is allowed
