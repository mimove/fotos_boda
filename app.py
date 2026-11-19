import hashlib
import hmac
import io
import json
import os
import re
import secrets
import time
import tempfile
import zipfile
import warnings
from urllib.parse import parse_qs, urlsplit
from functools import wraps
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_file
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
PHOTO_ROOT = Path(os.environ.get('PHOTO_ROOT', ROOT / 'files')).resolve()
DATA = Path(os.environ.get('DATA_DIR', ROOT / 'data'))
DATA.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
SECRET = os.environ.get('APP_SECRET', 'local-development-only').encode()
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
Image.MAX_IMAGE_PIXELS = 50_000_000


def photos():
    return {hashlib.sha256(str(p.relative_to(PHOTO_ROOT)).encode()).hexdigest()[:24]: p
            for p in sorted(PHOTO_ROOT.rglob('*')) if p.is_file() and p.suffix.lower() in EXTENSIONS}


def gallery_category(path):
    """Classify public gallery photos; face search continues to use all files."""
    collection = path.parent.name
    match = re.search(r'\.(\d+)\.[^.]+$', path.name)
    if not match or collection not in {'Todos_Color', 'Todos_BN'}:
        return None
    number = int(match.group(1))
    if collection == 'Todos_Color':
        if 48 <= number <= 129:
            return None
        moment = 'desayuno' if number < 48 else 'iglesia' if number < 361 else 'banquete'
        style = 'color'
    else:
        if 37 <= number <= 104:
            return None
        moment = 'desayuno' if number < 37 else 'iglesia' if number < 145 else 'banquete'
        style = 'bn'
    return f'{moment}-{style}'


def selected():
    try:
        return json.loads((DATA / 'selected.json').read_text())
    except (FileNotFoundError, ValueError):
        return [photo_id for photo_id, path in photos().items() if gallery_category(path)]


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        if not ADMIN_PASSWORD or not auth or not secrets.compare_digest(auth.password or '', ADMIN_PASSWORD):
            return ('Se requiere acceso de administrador', 401, {'WWW-Authenticate': 'Basic realm="Wedding gallery"'})
        return fn(*args, **kwargs)
    return wrapped


def signed_url(photo_id):
    expires = str(int(time.time()) + 3600)
    sig = hmac.new(SECRET, f'{photo_id}:{expires}'.encode(), hashlib.sha256).hexdigest()
    return f'/photo/{photo_id}?expires={expires}&sig={sig}'


def valid_signature(photo_id, expires, signature):
    expected = hmac.new(SECRET, f'{photo_id}:{expires}'.encode(), hashlib.sha256).hexdigest()
    return (len(expires) <= 16 and expires.isascii() and expires.isdigit()
            and int(expires) >= time.time() and len(signature) == 64
            and signature.isascii() and hmac.compare_digest(signature, expected))


def items(ids):
    available = photos()
    return [{'id': i, 'url': signed_url(i), 'name': available[i].name} for i in ids if i in available]


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/buscar')
def search_page():
    return render_template('buscar.html')


@app.get('/galeria')
def gallery_page():
    return render_template('galeria.html')


@app.get('/api/gallery')
def gallery():
    available = photos()
    chosen = [i for i in selected() if i in available and gallery_category(available[i])]
    result = items(chosen)
    for item in result:
        item['category'] = gallery_category(available[item['id']])
    return jsonify(result)


@app.post('/api/match')
def match():
    upload = request.files.get('selfie')
    if not upload:
        return jsonify(error='Elige primero una foto.'), 400
    try:
        import face_recognition
        import numpy as np
    except ImportError:
        return jsonify(error='El reconocimiento facial aún no está disponible. Ponte en contacto con los organizadores.'), 503
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload.stream) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP'} or source.width * source.height > Image.MAX_IMAGE_PIXELS:
                    raise ValueError('Unsupported image format or dimensions')
                image = ImageOps.exif_transpose(source).convert('RGB')
        image.thumbnail((1600, 1600))
        encodings = face_recognition.face_encodings(np.asarray(image))
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return jsonify(error='No se puede leer la imagen. Usa un JPEG, PNG o WebP de hasta 50 megapíxeles.'), 400
    if len(encodings) != 1:
        return jsonify(error='Usa una foto clara en la que aparezca una sola cara.'), 400
    try:
        index = json.loads((DATA / 'faces.json').read_text())
    except FileNotFoundError:
        return jsonify(error='Las fotos aún se están preparando. Ponte en contacto con los organizadores.'), 503
    matches = []
    for entry in index:
        if entry['encodings'] and min(face_recognition.face_distance(np.array(entry['encodings']), encodings[0])) <= 0.55:
            matches.append(entry['id'])
    return jsonify(items(matches))


@app.get('/photo/<photo_id>')
def photo(photo_id):
    path = photos().get(photo_id)
    if path is None:
        abort(404)
    expires = request.args.get('expires', '')
    signature = request.args.get('sig', '')
    if not valid_signature(photo_id, expires, signature):
        abort(403)
    if request.args.get('thumb') == '1':
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert('RGB')
            image.thumbnail((600, 600))
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=78)
            output.seek(0)
        return send_file(output, mimetype='image/jpeg', max_age=3600)
    return send_file(path, conditional=True, download_name=path.name,
                     as_attachment=request.args.get('download') == '1')


@app.post('/download-all')
def download_all():
    try:
        urls = json.loads(request.form.get('photos', ''))
    except (ValueError, TypeError):
        abort(400)
    if not isinstance(urls, list) or not urls or len(urls) > 2000:
        abort(400)
    available = photos()
    paths = []
    seen = set()
    for url in urls:
        if not isinstance(url, str) or len(url) > 500:
            abort(400)
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc or parsed.fragment or not parsed.path.startswith('/photo/'):
            abort(400)
        photo_id = parsed.path[len('/photo/'):]
        params = parse_qs(parsed.query)
        expires = params.get('expires', [''])[0]
        signature = params.get('sig', [''])[0]
        if photo_id not in available or not valid_signature(photo_id, expires, signature):
            abort(403)
        if photo_id not in seen:
            paths.append((photo_id, available[photo_id]))
            seen.add(photo_id)
    archive = tempfile.TemporaryFile()
    try:
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
            for photo_id, path in paths:
                bundle.write(path, arcname=f'{photo_id}-{path.name}')
        archive.seek(0)
        response = send_file(archive, mimetype='application/zip', as_attachment=True,
                             download_name='wedding-photos.zip')
        response.call_on_close(archive.close)
        return response
    except Exception:
        archive.close()
        raise


@app.get('/admin')
@admin_required
def admin():
    return render_template('admin.html')


@app.get('/api/admin/photos')
@admin_required
def admin_photos():
    chosen = set(selected())
    available = photos()
    eligible = [i for i, path in available.items() if gallery_category(path)]
    return jsonify([dict(item, selected=item['id'] in chosen) for item in items(eligible)])


@app.post('/api/admin/photos')
@admin_required
def save_selection():
    ids = request.get_json(silent=True)
    if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
        abort(400)
    available = photos()
    if any(i not in available for i in ids):
        abort(400)
    temp = DATA / 'selected.tmp'
    temp.write_text(json.dumps(list(dict.fromkeys(ids))))
    temp.replace(DATA / 'selected.json')
    return jsonify(ok=True)


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)), debug=False)
