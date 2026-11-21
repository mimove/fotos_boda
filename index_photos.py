"""Build an SFace index without changing the original photos or the old index."""
import fcntl
import json
import os
from pathlib import Path

from PIL import Image, ImageOps
from app import DATA, photos
from face_engine import INDEX_MODEL, INDEX_NAME, face_embeddings


def _read_index(path):
    try:
        data = json.loads(path.read_text())
        if data.get('model') != INDEX_MODEL or not isinstance(data.get('photos'), list):
            return {}
        return {entry['id']: entry for entry in data['photos']}
    except (FileNotFoundError, ValueError, AttributeError, KeyError, TypeError):
        return {}


def _write_index(path, entries):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'model': INDEX_MODEL, 'photos': entries}))
    os.replace(temporary, path)


def main():
    destination = DATA / INDEX_NAME
    partial = DATA / 'faces-sface.partial.json'
    with (DATA / '.faces-sface.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Face indexing is already running.', flush=True)
            return
        previous = _read_index(destination)
        previous.update(_read_index(partial))
        result = []
        all_photos = photos()
        if not all_photos:
            raise RuntimeError('No photos found; face index was not replaced')
        for number, (photo_id, path) in enumerate(all_photos.items(), 1):
            stat = path.stat()
            fingerprint = f'{stat.st_size}:{stat.st_mtime_ns}'
            entry = previous.get(photo_id)
            if not entry or entry.get('fingerprint') != fingerprint:
                with Image.open(path) as image:
                    image = ImageOps.exif_transpose(image).convert('RGB')
                    image.thumbnail((1600, 1600))
                    encodings = face_embeddings(image)
                entry = {'id': photo_id, 'fingerprint': fingerprint, 'encodings': [e.tolist() for e in encodings]}
            result.append(entry)
            if number % 20 == 0:
                _write_index(partial, result)
            print(f'{number}/{len(all_photos)} {path.name}: {len(entry["encodings"])} faces', flush=True)
        _write_index(destination, result)
        partial.unlink(missing_ok=True)
        print(f'Indexed {len(result)} photos in {destination}', flush=True)


if __name__ == '__main__':
    main()
