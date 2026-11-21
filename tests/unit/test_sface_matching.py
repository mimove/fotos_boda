import numpy as np
import pytest

from face_engine import cosine_matches


def test_cosine_threshold_and_zero_vectors():
    reference = np.array([1.0, 0.0])
    assert cosine_matches(reference, [[.5, 3 ** .5 / 2]], .5)
    assert not cosine_matches(reference, [[.49, (1 - .49 ** 2) ** .5]], .5)
    assert not cosine_matches(reference, [[0, 0]], .5)
    assert not cosine_matches(reference, [], .5)


def test_zero_reference_is_invalid():
    with pytest.raises(ValueError):
        cosine_matches([0, 0], [[1, 0]], .5)
