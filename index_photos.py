"""Build a face index locally; the original photographs remain untouched."""
import json
import os
from pathlib import Path

import face_recognition
import numpy as np
from PIL import Image, ImageOps
from app import DATA, photos


def main():
    destination = DATA / 'faces.json'
    try:
        previous = {entry['id']: entry for entry in json.loads(destination.read_text())}
    except (FileNotFoundError, ValueError):
        previous = {}
    result = []
    all_photos = photos()
    for number, (photo_id, path) in enumerate(all_photos.items(), 1):
        stat = path.stat()
        fingerprint = f'{stat.st_size}:{stat.st_mtime_ns}'
        entry = previous.get(photo_id)
        if not entry or entry.get('fingerprint') != fingerprint:
            try:
                with Image.open(path) as image:
                    image = ImageOps.exif_transpose(image).convert('RGB')
                    image.thumbnail((1600, 1600))
                    encodings = face_recognition.face_encodings(np.asarray(image))
                entry = {'id': photo_id, 'fingerprint': fingerprint, 'encodings': [e.tolist() for e in encodings]}
            except Exception as exc:
                print(f'Skipped {path}: {exc}', flush=True)
                continue
        result.append(entry)
        if number % 20 == 0:
            temporary = destination.with_suffix('.tmp')
            temporary.write_text(json.dumps(result))
            os.replace(temporary, destination)
        print(f'{number}/{len(all_photos)} {path.name}: {len(entry["encodings"])} faces', flush=True)
    temporary = destination.with_suffix('.tmp')
    temporary.write_text(json.dumps(result))
    os.replace(temporary, destination)
    print(f'Indexed {len(result)} photos in {destination}')


if __name__ == '__main__':
    main()
