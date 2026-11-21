import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import index_photos


def test_index_is_atomic_and_does_not_use_old_model(tmp_path, monkeypatch):
    original = tmp_path / 'faces.json'
    original.write_text('old index')
    destination = tmp_path / 'faces-sface.json'
    photo = tmp_path / 'photo.jpg'
    Image.new('RGB', (20, 20)).save(photo)
    monkeypatch.setattr(index_photos, 'DATA', tmp_path)
    monkeypatch.setattr(index_photos, 'photos', lambda: {'id': photo})
    monkeypatch.setattr(index_photos, 'face_embeddings', lambda image: [np.array([1.0, 0.0])])
    index_photos.main()
    data = json.loads(destination.read_text())
    assert data['model'] == index_photos.INDEX_MODEL
    assert data['photos'][0]['encodings'] == [[1.0, 0.0]]
    assert original.read_text() == 'old index'


def test_failed_reindex_preserves_previous_index(tmp_path, monkeypatch):
    destination = tmp_path / 'faces-sface.json'
    destination.write_text('previous index')
    photo = tmp_path / 'photo.jpg'
    Image.new('RGB', (20, 20)).save(photo)
    monkeypatch.setattr(index_photos, 'DATA', tmp_path)
    monkeypatch.setattr(index_photos, 'photos', lambda: {'id': photo})
    def fail(image):
        raise RuntimeError('model failure')
    monkeypatch.setattr(index_photos, 'face_embeddings', fail)
    with pytest.raises(RuntimeError):
        index_photos.main()
    assert destination.read_text() == 'previous index'


def test_empty_photo_directory_does_not_replace_existing_index(tmp_path, monkeypatch):
    destination = tmp_path / 'faces-sface.json'
    destination.write_text('previous index')
    monkeypatch.setattr(index_photos, 'DATA', tmp_path)
    monkeypatch.setattr(index_photos, 'photos', lambda: {})
    with pytest.raises(RuntimeError, match='No photos'):
        index_photos.main()
    assert destination.read_text() == 'previous index'
