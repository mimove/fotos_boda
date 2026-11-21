# Offline face evaluation

These tools are experimental and are not part of the deployed application. Do not commit photographs, face vectors, labels, model weights, or comparison results.

`tile_faces.extract_tile_vectors` detects faces in four overlapping crops using an existing YuNet detector and SFace recognizer. `face_eval.py` compares image-level SFace scores with manual labels, then reports true positives (tp), false negatives (fn), false positives (fp), and true negatives (tn). A crop match is added to a full-image match; the two thresholds may be specified separately. This increases the number of comparisons and can increase false matches. Thresholds selected using the same sample cannot establish performance on new photos.

The evaluator expects a CSV with `path` and `sface_cosine`, a JSON array of `{ "path": "...", "answer": "yes|no|unsure|" }`, and a JSON array of `{ "path": "...", "scores": { "person-id": 0.5 } }`. Missing scores are represented by `null` or an empty CSV field. Missing paths and duplicate photos are errors. Uncertain or unanswered labels are excluded. Use `--limit` only when the rows were ordered in advance, for example, to separate a random sample from additional selected matches.

```sh
python evaluation/face_eval.py --comparison comparison.csv --labels labels.json \
  --tiles tiles.json --person guest --limit 60
```

Install test dependencies in an isolated environment with `pip install -r requirements-dev.txt -r evaluation/requirements.txt`, then run `python -m pytest -q`. To include the real-model smoke test, set `EVAL_YUNET_MODEL` and `EVAL_SFACE_MODEL` to local OpenCV Zoo ONNX files. Optionally set `EVAL_REFERENCE_PHOTO` to a local photo with a visible face to check that real models extract finite vectors. The standard tests use synthetic data; these smoke tests do not establish recognition accuracy.

Tests are grouped under `tests/unit`, `tests/integration`, and `tests/e2e`. Run a group with, for example, `python -m pytest -q tests/integration`. The current end-to-end test exercises the evaluation CLI, not a browser.
