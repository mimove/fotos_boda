from pathlib import Path

import app


def test_gallery_api_and_navigation_include_dance(monkeypatch):
    available = {
        'banquet': Path('/photos/Todos_Color/Ana y Miguel.0720.JPG'),
        'dance': Path('/photos/Todos_Color/Ana y Miguel.0721.JPG'),
        'church': Path('/photos/Todos_Color/Ana y Miguel.0782.JPG'),
        'church2': Path('/photos/Todos_Color/Ana y Miguel.0783.JPG'),
        'bn': Path('/photos/Todos_BN/Ana y Miguel.0721.JPG'),
    }
    monkeypatch.setattr(app, 'photos', lambda: available)
    monkeypatch.setattr(app, 'selected', lambda: list(available))
    monkeypatch.setitem(app.app.config, 'GUEST_PASSWORD', 'testpassword')
    client = app.app.test_client()
    with client.session_transaction() as session:
        session['guest_auth'] = app.guest_token('testpassword')
    result = client.get('/api/gallery').get_json()
    assert {item['id']: item['category'] for item in result} == {
        'banquet': 'banquete-color', 'dance': 'baile-color',
        'church': 'iglesia-color', 'church2': 'iglesia-color', 'bn': 'banquete-bn',
    }
    page = client.get('/galeria').get_data(as_text=True)
    assert 'href="#baile"' in page
    assert 'id="gallery-baile-color"' in page
    assert 'id="gallery-baile-bn"' not in page
