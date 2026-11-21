import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JSC = '/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc'


@unittest.skipUnless(Path(JSC).exists() or shutil.which('jsc'), 'JavaScriptCore is not installed')
class PhotoPreviewTests(unittest.TestCase):
    def test_preview_preserves_and_updates_selected_photos(self):
        source = (ROOT / 'static/app.js').read_text()
        source = source.split('// Photo previews stay on the same page, preserving the current selection.\n', 1)[1]
        source = source.split('\nupdateSelection();\nif (document.querySelector', 1)[0]
        harness = r'''
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.listeners = {}; this.dataset = {}; this.attributes = {}; const classes = new Set(); this.classList = {add: x => classes.add(x), remove: x => classes.delete(x), contains: x => classes.has(x)}; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  append(...children) { this.children.push(...children); }
  replaceChildren() { this.children = []; }
  setAttribute(name, value) { this.attributes[name] = value; }
  getAttribute(name) { return this[name] || this.attributes[name]; }
  removeAttribute(name) { delete this[name]; }
  showModal() { this.open = true; }
  close() { this.open = false; if (this.listeners.close) this.listeners.close(); }
}
const names = ['photo-preview-dialog', 'photo-preview-image', 'photo-preview-placeholder', 'select-preview-photo', 'close-photo-preview', 'preview-previous', 'preview-next'];
const nodes = Object.fromEntries(names.map(name => [name, new Element(name)]));
let canvasDraws = 0;
const document = {querySelector: selector => nodes[selector.slice(1)], createElement: tag => {
  const element = new Element(tag);
  if (tag === 'canvas') {
    element.getContext = () => ({drawImage() { canvasDraws++; }});
    element.toDataURL = () => 'data:image/jpeg;base64,dGVzdA==';
  }
  return element;
}};
const selectedPhotos = new Map([['other', '/photo/other']]);
let updates = 0;
function updateSelection() { updates++; }
function savePhotoUrl(url) { return url + '&save=1&tz=0'; }
''' + source + r'''
const container = new Element('grid');
const photos = [{id: 'one', url: '/photo/one?sig=1', name: 'one.jpg'}, {id: 'two', url: '/photo/two?sig=2', name: 'two.jpg'}];
previewPhotos = photos;
grid(container, [photos[0]]);
const nextSection = new Element('grid');
grid(nextSection, [photos[1]]);
const card = container.children[0];
const selection = card.children[0];
const previewButton = card.children[1];
const thumbnail = selection.children[0];
thumbnail.complete = true;
thumbnail.naturalWidth = 600;
thumbnail.naturalHeight = 400;
if (selection.tag !== 'label' || previewButton.tag !== 'button') throw new Error('Separate controls missing');
previewButton.listeners.click();
if (!photoPreview.open || photoPreviewImage.src !== '/photo/one?sig=1&save=1&tz=0') throw new Error('Preview did not open a dated copy');
if (nodes['photo-preview-placeholder'].src !== 'data:image/jpeg;base64,dGVzdA==' || canvasDraws !== 1) throw new Error('Loaded thumbnail not reused');
if (!nodes['preview-previous'].disabled || nodes['preview-next'].disabled) throw new Error('Wrong navigation bounds');
if (!selectedPhotos.has('other')) throw new Error('Existing selection lost');
selectPreviewPhoto.listeners.click();
if (!selectedPhotos.has('one') || selectPreviewPhoto.attributes['aria-pressed'] !== 'true') throw new Error('Selection failed');
const previousLoad = photoPreviewImage.onload;
nodes['preview-next'].listeners.click();
if (photoPreviewImage.src !== '/photo/two?sig=2&save=1&tz=0' || !nodes['preview-next'].disabled) throw new Error('Next photo failed');
if (photoPreviewPlaceholder.src !== '/photo/two?sig=2&thumb=1') throw new Error('Unloaded thumbnail fallback failed');
if (!selectedPhotos.has('one') || selectPreviewPhoto.attributes['aria-pressed'] !== 'false') throw new Error('Selection lost when navigating');
previousLoad();
if (photoPreviewImage.classList.contains('is-ready')) throw new Error('Old image load revealed a new image too soon');
photoPreviewImage.onload();
if (!photoPreviewImage.classList.contains('is-ready')) throw new Error('Full image not shown after load');
nodes['preview-previous'].listeners.click();
if (photoPreviewImage.src !== '/photo/one?sig=1&save=1&tz=0') throw new Error('Previous photo failed');
let prevented = false;
photoPreview.listeners.keydown({key:'ArrowRight', preventDefault() { prevented = true; }});
if (!prevented || photoPreviewImage.src !== '/photo/two?sig=2&save=1&tz=0') throw new Error('Keyboard navigation failed');
nodes['preview-previous'].listeners.click();
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
