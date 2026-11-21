import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
JSC = '/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc'


def test_dance_is_rendered_and_included_in_preview_order():
    executable = JSC if Path(JSC).exists() else shutil.which('jsc')
    if not executable:
        pytest.skip('JavaScriptCore is not installed')
    source = (ROOT / 'static/app.js').read_text()
    source = source[source.index('const galleryGroups ='):source.index("if (document.querySelector('#selfie'))")]
    harness = r'''
const nodes = {};
const document = {querySelector(selector) { return nodes[selector] ||= {hidden: false}; }};
const previewThumbnails = new Map();
let previewPhotos = [];
function grid(node, photos) { node.photos = photos; }
function updateSelection() {
  if (nodes['#gallery-baile-color'].photos[0].id !== 'dance') throw new Error('Dance missing from gallery');
  if (nodes['#baile'].hidden || nodes['#group-baile-color'].hidden) throw new Error('Dance hidden');
  if (previewPhotos.map(p => p.id).join(',') !== 'church,banquet,dance') throw new Error('Wrong preview order');
  print('PASS');
}
function fetch() { return {then(first) { const photos = first({ok: true, json() { return [
  {id:'dance', category:'baile-color'}, {id:'church', category:'iglesia-color'},
  {id:'banquet', category:'banquete-color'}
]; }}); return {then(second) { second(photos); return {catch() {}}; }}; }}; }
if (true) {
''' + source
    result = subprocess.run([executable, '-e', harness], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert 'PASS' in result.stdout
