import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSC = '/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc'


@unittest.skipUnless(Path(JSC).exists() or shutil.which('jsc'), 'JavaScriptCore is not installed')
class PhotoPreviewTests(unittest.TestCase):
    def test_preview_preserves_and_updates_selected_photos(self):
        source = (ROOT / 'static/app.js').read_text()
        source = source.split('// Photo previews stay on the same page, preserving the current selection.\n', 1)[1]
        source = source.split('\nupdateSelection();\nif (document.querySelector', 1)[0]
        harness = r'''
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; this.dataset = {}; this.attributes = {}; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this[name]; }
  showModal() { this.open = true; }
  close() { this.open = false; if (this.listeners.close) this.listeners.close(); }
}
const names = ['photo-preview-dialog', 'photo-preview-image', 'select-preview-photo', 'close-photo-preview'];
const nodes = Object.fromEntries(names.map(name => [name, new Element(name)]));
const document = {querySelector: selector => nodes[selector.slice(1)], createElement: tag => new Element(tag)};
const selectedPhotos = new Map([['other', '/photo/other']]);
let updates = 0;
function updateSelection() { updates++; }
''' + source + r'''
const container = new Element('grid');
grid(container, [{id: 'one', url: '/photo/one?sig=1', name: 'one.jpg'}]);
const card = container.children[0];
const selection = card.children[0];
const previewButton = card.children[1];
if (selection.tag !== 'label' || previewButton.tag !== 'button') throw new Error('Separate controls missing');
previewButton.listeners.click();
if (!photoPreview.open || photoPreviewImage.src !== '/photo/one?sig=1') throw new Error('Preview did not open original');
if (!selectedPhotos.has('other')) throw new Error('Existing selection lost');
selectPreviewPhoto.listeners.click();
if (!selectedPhotos.has('one') || selectPreviewPhoto.attributes['aria-pressed'] !== 'true') throw new Error('Selection failed');
nodes['close-photo-preview'].listeners.click();
if (photoPreview.open || !selectedPhotos.has('one') || !selectedPhotos.has('other')) throw new Error('Selection lost on close');
previewButton.listeners.click();
selectPreviewPhoto.listeners.click();
if (selectedPhotos.has('one') || !selectedPhotos.has('other') || updates !== 2) throw new Error('Deselect failed');
print('PASS');
'''
        result = subprocess.run([JSC if Path(JSC).exists() else 'jsc', '-e', harness], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS', result.stdout, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
