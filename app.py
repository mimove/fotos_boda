import hashlib
import hmac
import io
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import time
import tempfile
import zipfile
import warnings
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, unquote, urlsplit
from functools import lru_cache, wraps
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, session, url_for
from PIL import Image, ImageOps
import piexif

ROOT = Path(__file__).resolve().parent
PHOTO_ROOT = Path(os.environ.get('PHOTO_ROOT', ROOT / 'files')).resolve()
DATA = Path(os.environ.get('DATA_DIR', ROOT / 'data'))
DATA.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
SECRET = os.environ.get('APP_SECRET', 'local-development-only').encode()
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
app.secret_key = SECRET
app.config.update(
    GUEST_PASSWORD=os.environ.get('GUEST_PASSWORD', ''),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1',
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
FACE_DISTANCE_THRESHOLD = 0.65
Image.MAX_IMAGE_PIXELS = 50_000_000
XMP_HEADER = b'http://ns.adobe.com/xap/1.0/\x00'
XMP_DATE_TAGS = rb'(?:photoshop:DateCreated|xmp:CreateDate|xmp:ModifyDate|xmp:MetadataDate|exif:DateTimeOriginal|exif:DateTimeDigitized|tiff:DateTime)'


def guest_token(password):
    return hmac.new(SECRET, b'guest-access:' + password.encode('utf-8'), hashlib.sha256).hexdigest()


def login_allowed(record_failure=False, clear=False):
    forwarded = request.headers.get('CF-Connecting-IP', '')
    try:
        client_ip = str(ipaddress.ip_address(forwarded))
    except ValueError:
        client_ip = request.remote_addr or 'unknown'
    client = hmac.new(SECRET, client_ip.encode('utf-8'), hashlib.sha256).hexdigest()
    now = time.time()
    with sqlite3.connect(DATA / 'guest-login.sqlite3', timeout=5) as db:
        db.execute('CREATE TABLE IF NOT EXISTS attempts (client TEXT PRIMARY KEY, failures INTEGER NOT NULL, first_failure REAL NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM attempts WHERE first_failure <= ?', (now - 600,))
        row = db.execute('SELECT failures FROM attempts WHERE client = ?', (client,)).fetchone()
        if row and row[0] >= 10:
            return False
        if clear:
            db.execute('DELETE FROM attempts WHERE client = ?', (client,))
        elif record_failure:
            db.execute('INSERT INTO attempts VALUES (?, 1, ?) ON CONFLICT(client) DO UPDATE SET failures = failures + 1', (client, now))
    return True


@app.before_request
def require_guest_access():
    password = app.config['GUEST_PASSWORD']
    if not password:
        return 'La galería aún no está configurada. Ponte en contacto con los organizadores.', 503
    if request.endpoint == 'guest_login':
        return None
    if not hmac.compare_digest(session.get('guest_auth', ''), guest_token(password)):
        target = request.full_path.rstrip('?') if request.method in {'GET', 'HEAD'} else '/'
        return redirect(url_for('guest_login', next=target))
    return None


@app.after_request
def private_responses(response):
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@app.route('/login', methods=['GET', 'POST'])
def guest_login():
    error = None
    target = request.values.get('next', '/')
    parsed = urlsplit(target)
    decoded_path = unquote(parsed.path)
    if (parsed.scheme or parsed.netloc or not decoded_path.startswith('/') or decoded_path.startswith('//')
            or '\\' in decoded_path or any(ord(c) < 32 for c in decoded_path)):
        target = '/'
    if request.method == 'POST':
        if not login_allowed():
            return render_template('login.html', error='Demasiados intentos. Prueba de nuevo dentro de unos minutos.', next=target), 429
        supplied = request.form.get('password', '')
        expected = app.config['GUEST_PASSWORD']
        if secrets.compare_digest(supplied.encode('utf-8'), expected.encode('utf-8')):
            login_allowed(clear=True)
            session.clear()
            session.permanent = True
            session['guest_auth'] = guest_token(expected)
            return redirect(target)
        login_allowed(record_failure=True)
        error = 'La contraseña no es correcta. Inténtalo de nuevo.'
    return render_template('login.html', error=error, next=target), 401 if error else 200


def download_time(raw_offset):
    try:
        offset = int(raw_offset)
    except (TypeError, ValueError):
        abort(400)
    if not -840 <= offset <= 720:
        abort(400)
    return datetime.now(timezone(timedelta(minutes=-offset)))


def update_xmp_dates(jpeg, stamp, exif):
    """Replace JPEG EXIF and update XMP dates without changing image pixels."""
    if len(exif) + 2 > 65535:
        raise ValueError('EXIF metadata is too large')
    result = [jpeg[:2], b'\xff\xe1' + (len(exif) + 2).to_bytes(2, 'big') + exif]
    position = 2
    while position < len(jpeg):
        if jpeg[position:position + 2] == b'\xff\xda':
            result.append(jpeg[position:])
            return b''.join(result)
        if jpeg[position] != 0xff or position + 4 > len(jpeg):
            raise ValueError('Invalid JPEG segment')
        length = int.from_bytes(jpeg[position + 2:position + 4], 'big')
        end = position + length + 2
        if length < 2 or end > len(jpeg):
            raise ValueError('Invalid JPEG segment length')
        segment = jpeg[position:end]
        if segment[:2] == b'\xff\xe1' and segment[4:].startswith(b'Exif\x00\x00'):
            position = end
            continue
        if segment[:2] == b'\xff\xe1' and segment[4:].startswith(XMP_HEADER):
            payload = segment[4:]
            value = stamp.isoformat(timespec='seconds').encode('ascii')
            payload = re.sub(rb'(' + XMP_DATE_TAGS + rb'\s*=\s*["\'])([^"\']*)(["\'])', lambda m: m.group(1) + value + m.group(3), payload)
            payload = re.sub(rb'(<(' + XMP_DATE_TAGS + rb')\s*>)([^<]*)(</\2\s*>)', lambda m: m.group(1) + value + m.group(4), payload)
            if len(payload) + 2 > 65535:
                raise ValueError('XMP metadata is too large')
            segment = b'\xff\xe1' + (len(payload) + 2).to_bytes(2, 'big') + payload
        result.append(segment)
        position = end
    raise ValueError('JPEG image data missing')


def dated_photo(path, stamp):
    """Return a JPEG copy with current capture dates, retaining its encoded pixels."""
    data = path.read_bytes()
    if not data.startswith(b'\xff\xd8'):
        return data
    exif = piexif.load(data)
    exif_date = stamp.strftime('%Y:%m:%d %H:%M:%S')
    offset = stamp.strftime('%z')
    offset = offset[:3] + ':' + offset[3:]
    exif['0th'][piexif.ImageIFD.DateTime] = exif_date
    for tag in (piexif.ExifIFD.DateTimeOriginal, piexif.ExifIFD.DateTimeDigitized):
        exif['Exif'][tag] = exif_date
    for tag in (piexif.ExifIFD.OffsetTime, piexif.ExifIFD.OffsetTimeOriginal, piexif.ExifIFD.OffsetTimeDigitized):
        exif['Exif'][tag] = offset
    for tag in (piexif.ExifIFD.SubSecTime, piexif.ExifIFD.SubSecTimeOriginal, piexif.ExifIFD.SubSecTimeDigitized):
        exif['Exif'].pop(tag, None)
    return update_xmp_dates(data, stamp, piexif.dump(exif))


def _scan_photo_paths(root):
    return {hashlib.sha256(str(p.relative_to(root)).encode()).hexdigest()[:24]: p
            for p in sorted(root.rglob('*')) if p.is_file() and p.suffix.lower() in EXTENSIONS}


@lru_cache(maxsize=4)
def _cached_photo_paths(root, interval):
    return _scan_photo_paths(root)


def photos():
    # Refresh new or removed files within 30 seconds without rescanning on every image request.
    return _cached_photo_paths(PHOTO_ROOT, int(time.monotonic() // 30))


def _render_thumbnail(path):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        image.thumbnail((600, 600))
        output = io.BytesIO()
        image.save(output, format='JPEG', quality=78)
        return output.getvalue()


@lru_cache(maxsize=512)
def _cached_thumbnail(path, mtime_ns, size):
    return _render_thumbnail(path)


def thumbnail_bytes(path):
    stat = path.stat()
    return _cached_thumbnail(path, stat.st_mtime_ns, stat.st_size)


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
        if entry['encodings'] and min(face_recognition.face_distance(np.array(entry['encodings']), encodings[0])) <= FACE_DISTANCE_THRESHOLD:
            matches.append(entry['id'])
    return jsonify(items(matches))


@app.get('/photo/<photo_id>')
def photo(photo_id):
    path = photos().get(photo_id)
    if path is None or not path.is_file():
        abort(404)
    expires = request.args.get('expires', '')
    signature = request.args.get('sig', '')
    if not valid_signature(photo_id, expires, signature):
        abort(403)
    if request.args.get('thumb') == '1':
        return send_file(io.BytesIO(thumbnail_bytes(path)), mimetype='image/jpeg')
    if request.args.get('save') == '1':
        stamp = download_time(request.args.get('tz', '0'))
        output = io.BytesIO(dated_photo(path, stamp))
        response = send_file(output, download_name=path.name)
        response.headers['Cache-Control'] = 'private, no-store'
        return response
    return send_file(path, conditional=True, download_name=path.name,
                     as_attachment=request.args.get('download') == '1')


@app.post('/download-all')
def download_all():
    stamp = download_time(request.form.get('tz', '0'))
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
                bundle.writestr(f'{photo_id}-{path.name}', dated_photo(path, stamp))
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
