import pytest

from evaluation.face_eval import evaluate, tile_boxes


def test_tile_boxes_cover_edges_with_overlap():
    boxes = tile_boxes(720, 1080)
    assert boxes == [(0, 0, 446, 669), (273, 0, 720, 669),
                     (0, 410, 446, 1080), (273, 410, 720, 1080)]
    assert boxes[0][2] > boxes[1][0] and boxes[0][3] > boxes[2][1]


def test_tile_boxes_reject_empty_image():
    with pytest.raises(ValueError):
        tile_boxes(0, 100)


def test_evaluate_counts_misses_false_matches_and_excluded():
    rows = [
        {'path': 'a', 'sface_cosine': '0.49'},
        {'path': 'b', 'sface_cosine': '0.51'},
        {'path': 'c', 'sface_cosine': ''},
        {'path': 'd', 'sface_cosine': '0.8'},
    ]
    labels = {'a': 'yes', 'b': 'no', 'c': 'yes', 'd': 'unsure'}
    tile = {'a': 0.56, 'b': 0.2, 'c': None, 'd': 0.9}
    result = evaluate(rows, labels, tile, .5, .55)
    assert result['baseline'] == {'tp': 0, 'fn': 2, 'fp': 1, 'tn': 0}
    assert result['with_tiles'] == {'tp': 1, 'fn': 1, 'fp': 1, 'tn': 0}
    assert result['excluded'] == 1


def test_missing_tile_data_fails_instead_of_biasing_results():
    with pytest.raises(ValueError, match='tile'):
        evaluate([{'path': 'a', 'sface_cosine': '0.9'}], {'a': 'yes'}, {}, .5, .5)
