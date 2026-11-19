const selectedPhotos = new Map();
try { sessionStorage.removeItem('fotos-boda-seleccion'); } catch (_) { /* Storage is optional. */ }
const selectionBar = document.querySelector('#selection-bar');
const selectionCount = document.querySelector('#selection-count');
function updateSelection() {
  const count = selectedPhotos.size;
  selectionBar.hidden = count === 0;
  selectionCount.textContent = count === 1 ? '1 foto seleccionada' : `${count} fotos seleccionadas`;
  document.querySelector('#selection-photos').value = JSON.stringify([...selectedPhotos.values()]);
  document.querySelectorAll('.select-photo input').forEach(input => {
    input.checked = selectedPhotos.has(input.dataset.photoId);
  });
}
document.querySelector('#clear-selection').addEventListener('click', () => {
  selectedPhotos.clear();
  updateSelection();
});
// Sharing original files lets supported phones offer to save them to Photos.
const saveDialog = document.querySelector('#save-photos-dialog');
const saveStatus = document.querySelector('#save-photos-status');
const shareButton = document.querySelector('#share-photos');
let saveUrls = [], saveIndex = 0, saveFiles = [], saveForm = null, saveRun = 0;
const phone = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
function canSharePhotos() {
  try {
    return phone && typeof saveDialog.showModal === 'function' && !!navigator.share && !!navigator.canShare &&
      navigator.canShare({files: [new File([''], 'foto.jpg', {type: 'image/jpeg'})]});
  } catch (_) { return false; }
}
async function preparePhotos() {
  const run = ++saveRun;
  const start = saveIndex;
  const batch = saveUrls.slice(start, start + 10);
  shareButton.disabled = true;
  saveStatus.textContent = `Preparando fotos ${start + 1}–${start + batch.length} de ${saveUrls.length}…`;
  try {
    const files = await Promise.all(batch.map(async (url, index) => {
      const response = await fetch(url);
      if (!response.ok) throw new Error('No se han podido cargar las fotos.');
      const blob = await response.blob();
      return new File([blob], `boda-${start + index + 1}.jpg`, {type: blob.type || 'image/jpeg'});
    }));
    if (run !== saveRun) return;
    if (!navigator.canShare({files})) throw new Error('El móvil no permite compartir este grupo de fotos.');
    saveFiles = files;
    saveStatus.textContent = `Fotos ${start + 1}–${start + batch.length} de ${saveUrls.length} listas para guardar.`;
    shareButton.disabled = false;
  } catch (error) {
    if (run === saveRun) saveStatus.textContent = `${error.message} Puedes descargar el ZIP.`;
  }
}
for (const form of [document.querySelector('#selection-form'), document.querySelector('#download-matches')]) {
  if (!form) continue;
  form.addEventListener('submit', event => {
    if (!canSharePhotos()) return;
    event.preventDefault();
    saveForm = form;
    saveUrls = JSON.parse(form.elements.photos.value);
    if (!saveUrls.length) return;
    saveIndex = 0;
    saveDialog.showModal();
    preparePhotos();
  });
}
shareButton.addEventListener('click', async () => {
  shareButton.disabled = true;
  try {
    await navigator.share({files: saveFiles});
    saveIndex += saveFiles.length;
    if (saveIndex < saveUrls.length) preparePhotos();
    else saveStatus.textContent = 'Ya se han compartido todos los grupos. Comprueba que estén guardados en tu aplicación de fotos.';
  } catch (error) {
    saveStatus.textContent = error.name === 'AbortError' ? 'No se ha completado. Puedes intentarlo de nuevo.' : 'No se han podido compartir las fotos. Puedes intentarlo de nuevo o descargar el ZIP.';
    shareButton.disabled = false;
  }
});
document.querySelector('#download-zip').addEventListener('click', () => {
  if (saveForm) saveForm.submit();
  saveDialog.close();
});
document.querySelector('#close-save-photos').addEventListener('click', () => saveDialog.close());
saveDialog.addEventListener('close', () => { saveRun++; });
const grid = (element, photos) => {
  element.replaceChildren();
  for (const photo of photos) {
    const card = document.createElement('label');
    card.className = 'photo-card';
    const image = document.createElement('img');
    image.src = photo.url + '&thumb=1';
    image.alt = 'Recuerdo de la boda';
    image.loading = 'lazy';
    const selectLabel = document.createElement('span');
    selectLabel.className = 'select-photo';
    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.dataset.photoId = photo.id;
    checkbox.checked = selectedPhotos.has(photo.id);
    if (checkbox.checked) selectedPhotos.set(photo.id, photo.url);
    checkbox.setAttribute('aria-label', `Seleccionar ${photo.name}`);
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) selectedPhotos.set(photo.id, photo.url);
      else selectedPhotos.delete(photo.id);
      updateSelection();
    });
    const labelText = document.createElement('span');
    labelText.textContent = 'Seleccionar';
    selectLabel.append(checkbox, labelText);
    card.append(image, selectLabel);
    element.append(card);
  }
};
updateSelection();
if (document.querySelector('#gallery-empty')) {
const galleryGroups = ['desayuno-color', 'desayuno-bn', 'iglesia-color', 'iglesia-bn', 'banquete-color', 'banquete-bn'];
fetch('/api/gallery').then(r => { if (!r.ok) throw new Error(); return r.json(); }).then(photos => {
  for (const group of galleryGroups) {
    const entries = photos.filter(photo => photo.category === group);
    grid(document.querySelector(`#gallery-${group}`), entries);
    document.querySelector(`#group-${group}`).hidden = entries.length === 0;
  }
  for (const moment of ['desayuno', 'iglesia', 'banquete']) {
    document.querySelector(`#${moment}`).hidden = !photos.some(photo => photo.category.startsWith(moment + '-'));
  }
  document.querySelector('#gallery-empty').hidden = photos.length > 0;
  updateSelection();
}).catch(() => {
  document.querySelector('#gallery-empty').hidden = false;
  document.querySelector('#gallery-empty').textContent = 'No se ha podido cargar la galería. Inténtalo de nuevo.';
});
}
if (document.querySelector('#selfie')) {
const status = document.querySelector('#status');
const cameraPanel = document.querySelector('#camera-panel');
const preview = document.querySelector('#camera-preview');
let cameraStream = null;
let cameraRequest = 0;
function stopCamera() {
  cameraRequest++;
  if (cameraStream) cameraStream.getTracks().forEach(track => track.stop());
  cameraStream = null;
  preview.srcObject = null;
  cameraPanel.hidden = true;
}
async function searchPhoto(file) {
  const results = document.querySelector('#results');
  results.hidden = true;
  status.textContent = 'Buscando tus fotos…';
  const body = new FormData();
  body.append('selfie', file, 'selfie.jpg');
  try {
    const response = await fetch('/api/match', {method:'POST', body});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Algo ha salido mal.');
    grid(document.querySelector('#matches'), data);
    document.querySelector('#results-count').textContent = data.length === 1 ? '1 foto encontrada' : `${data.length} fotos encontradas`;
    document.querySelector('#match-photos').value = JSON.stringify(data.map(photo => photo.url));
    document.querySelector('#download-matches').hidden = data.length === 0;
    updateSelection();
    results.hidden = false;
    status.textContent = data.length ? `Hemos encontrado ${data.length} fotos.` : 'No hemos encontrado coincidencias. Prueba con otra foto clara.';
    if (data.length) results.scrollIntoView({behavior:'smooth'});
  } catch (error) { status.textContent = error.message || 'No se ha podido realizar la búsqueda. Inténtalo de nuevo.'; }
}
function handlePhotoChoice(event) {
  const file = event.target.files[0];
  if (file) { stopCamera(); searchPhoto(file); }
  event.target.value = '';
}
document.querySelector('#selfie').addEventListener('change', handlePhotoChoice);
document.querySelector('#native-camera').addEventListener('change', handlePhotoChoice);
document.querySelector('#open-camera').addEventListener('click', async () => {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    status.textContent = 'Usa la cámara del dispositivo para hacerte una foto.';
    document.querySelector('#native-camera').click();
    return;
  }
  stopCamera();
  const requestId = cameraRequest;
  status.textContent = 'Permite el acceso a la cámara en tu navegador.';
  try {
    const stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'user'}, audio: false});
    if (requestId !== cameraRequest) { stream.getTracks().forEach(track => track.stop()); return; }
    cameraStream = stream;
    preview.srcObject = stream;
    cameraPanel.hidden = false;
    status.textContent = 'Coloca tu cara en el encuadre y haz una foto.';
  } catch (error) {
    if (requestId !== cameraRequest) return;
    status.textContent = error.name === 'NotAllowedError' ? 'Se ha denegado el acceso a la cámara. Permítelo en el navegador o elige una foto.' : 'No se ha podido abrir la cámara. Comprueba que esté disponible o elige una foto.';
  }
});
document.querySelector('#capture-photo').addEventListener('click', () => {
  if (!preview.videoWidth || !preview.videoHeight) { status.textContent = 'La cámara se está iniciando. Inténtalo de nuevo en un momento.'; return; }
  const canvas = document.createElement('canvas');
  canvas.width = preview.videoWidth;
  canvas.height = preview.videoHeight;
  canvas.getContext('2d').drawImage(preview, 0, 0);
  canvas.toBlob(blob => {
    if (!blob) { status.textContent = 'No se ha podido hacer la foto. Inténtalo de nuevo.'; return; }
    stopCamera();
    searchPhoto(blob);
  }, 'image/jpeg', 0.9);
});
document.querySelector('#close-camera').addEventListener('click', () => { stopCamera(); status.textContent = ''; });
window.addEventListener('pagehide', stopCamera);

}
