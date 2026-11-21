from pathlib import Path

import pytest

from app import gallery_category


@pytest.mark.parametrize(('folder', 'number', 'expected'), [
    ('Todos_Color', 720, 'banquete-color'),
    ('Todos_Color', 721, 'baile-color'),
    ('Todos_Color', 781, 'baile-color'),
    ('Todos_Color', 782, 'iglesia-color'),
    ('Todos_Color', 783, 'iglesia-color'),
    ('Todos_Color', 784, 'baile-color'),
    ('Todos_BN', 721, 'banquete-bn'),
    ('Todos_BN', 782, 'banquete-bn'),
])
def test_dance_and_church_category_boundaries(folder, number, expected):
    assert gallery_category(Path('/photos') / folder / f'Ana y Miguel.{number:04d}.JPG') == expected
