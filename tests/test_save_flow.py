import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSC = '/System/Library/Frameworks/JavaScriptCore.framework/Versions/A/Helpers/jsc'


@unittest.skipUnless(Path(JSC).exists() or shutil.which('jsc'), 'JavaScriptCore is not installed')
class SaveFlowTests(unittest.TestCase):
    def test_share_can_be_retried_and_manual_batches_advance(self):
        source = (ROOT / 'static/app.js').read_text()
        source = source.split('// Prepare dated copies', 1)[1].split('\n', 1)[1].split('// Photo previews', 1)[0]
        harness = r'''
class Element {
  constructor() { this.listeners = {}; this.hidden = false; this.disabled = false; this.children = []; this.textContent = ''; }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  replaceChildren() { this.children = []; }
  append(child) { this.children.push(child); }
  showModal() {}
  close() { if (this.listeners.close) this.listeners.close(); }
}
const ids = ['save-photos-dialog', 'save-photos-status', 'share-photos', 'next-photos',
  'manual-photos', 'manual-photos-grid', 'save-manually', 'download-zip', 'close-save-photos', 'selection-form'];
const nodes = Object.fromEntries(ids.map(id => [id, new Element()]));
const urls = Array.from({length: 11}, (_, i) => '/photo/' + i);
nodes['selection-form'].elements = {photos: {value: JSON.stringify(urls)}, tz: {value: ''}};
const document = {
  querySelector: selector => nodes[selector.slice(1)] || null,
  createElement: () => new Element()
};
const navigator = {userAgent: 'iPhone', canShare: () => true,
  share: () => new Promise(() => {})};
class File { constructor(parts, name, options) { this.name = name; this.type = options.type; } }
const fetch = async () => ({ok: true, blob: async () => ({type: 'image/jpeg'})});
''' + source + r'''
async function test() {
  nodes['selection-form'].listeners.submit({preventDefault() {}});
  for (let i = 0; i < 20; i++) await Promise.resolve();
  if (shareButton.disabled) throw new Error('First batch not prepared');
  shareButton.listeners.click();
  if (shareButton.disabled || nextPhotos.hidden) throw new Error('Pending share prevented retry or next batch');
  nodes['save-manually'].listeners.click();
  if (manualPhotos.hidden || manualGrid.children.length !== 10) throw new Error('Manual batch missing');
  nextPhotos.listeners.click();
  for (let i = 0; i < 20; i++) await Promise.resolve();
  if (!nextPhotos.hidden || shareButton.disabled) throw new Error('Last batch not ready');
  nodes['save-manually'].listeners.click();
  if (manualGrid.children.length !== 1 || !manualGrid.children[0].src.startsWith('/photo/10&save=1&tz=')) throw new Error('Wrong final batch');
  saveDialog.close();
  navigator.canShare = () => false;
  nodes['selection-form'].listeners.submit({preventDefault() {}});
  if (!shareButton.hidden) throw new Error('Unsupported share should be hidden');
  nodes['save-manually'].listeners.click();
  if (manualPhotos.hidden || manualGrid.children.length !== 10) throw new Error('Manual fallback unavailable');
  print('PASS');
}
test().catch(error => print('FAIL: ' + error.message));
'''
        result = subprocess.run([JSC if Path(JSC).exists() else 'jsc', '-e', harness], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS', result.stdout, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
