"""Compare labelled face-search scores without accessing or changing the live app."""
import argparse
import csv
import json
import math


def tile_boxes(width, height):
    """Return overlapping crops whose outer edges cover the whole image."""
    if width < 3 or height < 3:
        raise ValueError('Image dimensions must be at least three pixels')
    x0, y0 = int(width * .38), int(height * .38)
    x1, y1 = int(width * .62), int(height * .62)
    return [(0, 0, x1, y1), (x0, 0, width, y1),
            (0, y0, x1, height), (x0, y0, width, height)]


def _score(value):
    if value is None or value == '':
        return None
    value = float(value)
    if not math.isfinite(value) or not -1 <= value <= 1:
        raise ValueError('Similarity score must be finite and between -1 and 1')
    return value


def evaluate(rows, labels, tiles, threshold=.5, tile_threshold=.5):
    """Count image-level classifications, excluding uncertain/unanswered labels."""
    result = {'baseline': dict(tp=0, fn=0, fp=0, tn=0),
              'with_tiles': dict(tp=0, fn=0, fp=0, tn=0), 'excluded': 0}
    seen = set()
    for row in rows:
        path = row['path']
        if path in seen:
            raise ValueError('Duplicate comparison photo: ' + path)
        seen.add(path)
        if path not in labels:
            raise ValueError('Missing label for: ' + path)
        if path not in tiles:
            raise ValueError('Missing tile result for: ' + path)
        answer = labels[path]
        if answer in ('', 'unsure'):
            result['excluded'] += 1
            continue
        if answer not in ('yes', 'no'):
            raise ValueError('Invalid review answer for: ' + path)
        baseline, tile = _score(row['sface_cosine']), _score(tiles[path])
        matched = baseline is not None and baseline >= threshold
        tile_matched = tile is not None and tile >= tile_threshold
        for key, prediction in [('baseline', matched), ('with_tiles', matched or tile_matched)]:
            category = ('t' if (answer == 'yes') == prediction else 'f') + ('p' if prediction else 'n')
            result[key][category] += 1
    return result


def _unique_map(records, field):
    result = {}
    for record in records:
        path = record['path']
        if path in result:
            raise ValueError('Duplicate photo in input: ' + path)
        result[path] = record[field]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--labels', required=True)
    parser.add_argument('--tiles', required=True)
    parser.add_argument('--person', required=True)
    parser.add_argument('--threshold', type=float, default=.5)
    parser.add_argument('--tile-threshold', type=float, default=.5)
    parser.add_argument('--limit', type=int, help='Use the first N comparison rows, for a predefined sample')
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error('--limit must be positive')
    if not -1 <= args.threshold <= 1 or not -1 <= args.tile_threshold <= 1:
        parser.error('thresholds must be between -1 and 1')
    with open(args.comparison, newline='') as f:
        rows = list(csv.DictReader(f))
    if args.limit is not None:
        if len(rows) < args.limit:
            parser.error('comparison has fewer rows than --limit')
        rows = rows[:args.limit]
    with open(args.labels) as f:
        labels = _unique_map(json.load(f), 'answer')
    with open(args.tiles) as f:
        tile_records = _unique_map(json.load(f), 'scores')
    try:
        tile_scores = {path: scores[args.person] for path, scores in tile_records.items()}
        print(json.dumps(evaluate(rows, labels, tile_scores, args.threshold, args.tile_threshold)))
    except (KeyError, ValueError) as exc:
        parser.exit(2, f'Invalid evaluation data: {exc}\n')


if __name__ == '__main__':
    main()
