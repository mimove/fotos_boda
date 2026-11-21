#!/bin/sh
# Keep the gallery available while the separate face index is built or refreshed.
python index_photos.py &
exec gunicorn --bind 0.0.0.0:5000 --timeout 120 --workers 2 app:app
