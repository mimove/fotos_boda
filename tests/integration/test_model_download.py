import hashlib
import io

import pytest

import download_models


def test_download_checks_hash_and_keeps_existing_model_on_failure(tmp_path, monkeypatch):
    filename = 'model.onnx'
    expected = b'verified model'
    target = tmp_path / filename
    target.write_bytes(b'existing model')
    monkeypatch.setenv('FACE_MODEL_DIR', str(tmp_path))
    monkeypatch.setattr(download_models, 'MODELS', {filename: ('test', hashlib.sha256(expected).hexdigest())})
    monkeypatch.setattr(download_models, 'urlopen', lambda *args, **kwargs: io.BytesIO(b'bad download'))
    with pytest.raises(ValueError, match='Checksum mismatch'):
        download_models.main()
    assert target.read_bytes() == b'existing model'
    assert not target.with_suffix('.download').exists()
    monkeypatch.setattr(download_models, 'urlopen', lambda *args, **kwargs: io.BytesIO(expected))
    download_models.main()
    assert target.read_bytes() == expected
