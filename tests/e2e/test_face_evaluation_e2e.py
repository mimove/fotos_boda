import csv
import json
import subprocess
import sys
from pathlib import Path


def test_end_to_end_cli_reads_review_and_writes_json(tmp_path):
    comparison = tmp_path / 'comparison.csv'
    with comparison.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['path', 'sface_cosine'])
        writer.writeheader()
        writer.writerows([{'path': 'a.jpg', 'sface_cosine': '0.2'},
                          {'path': 'b.jpg', 'sface_cosine': '0.7'}])
    labels = tmp_path / 'review.json'
    labels.write_text(json.dumps([{'path': 'a.jpg', 'answer': 'yes'},
                                  {'path': 'b.jpg', 'answer': 'no'}]))
    tiles = tmp_path / 'tiles.json'
    tiles.write_text(json.dumps([{'path': 'a.jpg', 'scores': {'guest': .6}},
                                 {'path': 'b.jpg', 'scores': {'guest': .1}}]))
    cli = Path(__file__).resolve().parents[2] / 'evaluation' / 'face_eval.py'
    process = subprocess.run([sys.executable, str(cli), '--comparison', str(comparison),
                              '--labels', str(labels), '--tiles', str(tiles), '--person', 'guest'],
                             capture_output=True, text=True, check=True)
    result = json.loads(process.stdout)
    assert result['baseline'] == {'tp': 0, 'fn': 1, 'fp': 1, 'tn': 0}
    assert result['with_tiles'] == {'tp': 1, 'fn': 0, 'fp': 1, 'tn': 0}
