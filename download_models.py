"""Download and verify the OpenCV Zoo model files used by face search."""
import hashlib
import os
from pathlib import Path
from urllib.request import urlopen

MODELS = {
    'face_detection_yunet_2023mar.onnx': ('face_detection_yunet', '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'),
    'face_recognition_sface_2021dec.onnx': ('face_recognition_sface', '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79'),
}
BASE = 'https://github.com/opencv/opencv_zoo/raw/main/models'


def main():
    destination = Path(os.environ.get('FACE_MODEL_DIR', Path(__file__).resolve().parent / 'models'))
    destination.mkdir(parents=True, exist_ok=True)
    for filename, (folder, expected) in MODELS.items():
        target = destination / filename
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
            continue
        temporary = target.with_suffix('.download')
        try:
            with urlopen(f'{BASE}/{folder}/{filename}', timeout=120) as source, temporary.open('wb') as output:
                digest = hashlib.sha256()
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != expected:
                raise ValueError(f'Checksum mismatch for {filename}')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        print(f'Downloaded {filename}', flush=True)


if __name__ == '__main__':
    main()
