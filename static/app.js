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
// Prepare dated copies for the phone's photo library.
const saveDialog = document.querySelector('#save-photos-dialog');
const saveStatus = document.querySelector('#save-photos-status');
const shareButton = document.querySelector('#share-photos');
const nextPhotos = document.querySelector('#next-photos');
const manualPhotos = document.querySelector('#manual-photos');
const manualGrid = document.querySelector('#manual-photos-grid');
let saveUrls = [], saveIndex = 0, saveFiles = [], saveForm = null, saveRun = 0;
const phone = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
function savePhotoUrl(url) {
  return `${url}&save=1&tz=${new Date().getTimezoneOffset()}`;
}
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
  saveFiles = [];
  nextPhotos.hidden = true;
  manualPhotos.hidden = true;
  manualGrid.replaceChildren();
  shareButton.disabled = true;
  shareButton.hidden = !canSharePhotos();
  if (shareButton.hidden) {
    saveStatus.textContent = `Fotos ${start + 1}–${start + batch.length} de ${saveUrls.length}. Usa «Ver fotos para guardar».`;
    return;
  }
  saveStatus.textContent = `Preparando fotos ${start + 1}–${start + batch.length} de ${saveUrls.length}…`;
  try {
    const files = await Promise.all(batch.map(async (url, index) => {
      const response = await fetch(savePhotoUrl(url));
      if (!response.ok) throw new Error('No se han podido cargar las fotos.');
      const blob = await response.blob();
      return new File([blob], `boda-${start + index + 1}.jpg`, {type: blob.type || 'image/jpeg', lastModified: Date.now()});
    }));
    if (run !== saveRun) return;
    if (!navigator.canShare({files})) throw new Error('El móvil no permite compartir este grupo de fotos.');
    saveFiles = files;
    saveStatus.textContent = `Fotos ${start + 1}–${start + batch.length} de ${saveUrls.length} listas para guardar.`;
    shareButton.disabled = false;
  } catch (error) {
    if (run === saveRun) saveStatus.textContent = `${error.message} Usa «Ver fotos para guardar» o descarga el ZIP.`;
  }
}
for (const form of [document.querySelector('#selection-form'), document.querySelector('#download-matches')]) {
  if (!form) continue;
  form.addEventListener('submit', event => {
    form.elements.tz.value = String(new Date().getTimezoneOffset());
    if (!phone || typeof saveDialog.showModal !== 'function') return;
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
  if (!saveFiles.length) return;
  const run = saveRun;
  try {
    const sharing = navigator.share({files: saveFiles});
    nextPhotos.hidden = saveIndex + saveFiles.length >= saveUrls.length;
    saveStatus.textContent = 'En el menú del móvil, elige «Guardar imagen» o «Guardar imágenes». Si no aparece, pulsa «Ver fotos para guardar».';
    await sharing;
  } catch (error) {
    if (run !== saveRun) return;
    saveStatus.textContent = error.name === 'AbortError' ? 'No se ha completado. Puedes intentarlo de nuevo.' : 'No se han podido compartir las fotos. Puedes intentarlo de nuevo o descargar el ZIP.';
  }
});
nextPhotos.addEventListener('click', () => {
  saveIndex += Math.min(10, saveUrls.length - saveIndex);
  preparePhotos();
});
document.querySelector('#save-manually').addEventListener('click', () => {
  manualGrid.replaceChildren();
  for (const url of saveUrls.slice(saveIndex, saveIndex + 10)) {
    const image = document.createElement('img');
    image.src = savePhotoUrl(url);
    image.alt = 'Foto de la boda';
    manualGrid.append(image);
  }
  manualPhotos.hidden = false;
  nextPhotos.hidden = saveIndex + 10 >= saveUrls.length;
  saveStatus.textContent = 'Mantén pulsada cada foto de abajo para guardarla en tu móvil.';
});
document.querySelector('#download-zip').addEventListener('click', () => {
  if (saveForm) saveForm.submit();
  saveDialog.close();
});
document.querySelector('#close-save-photos').addEventListener('click', () => saveDialog.close());
saveDialog.addEventListener('close', () => { saveRun++; });
// Photo previews stay on the same page, preserving the current selection.
const photoPreview = document.querySelector('#photo-preview-dialog');
const photoPreviewImage = document.querySelector('#photo-preview-image');
photoPreviewImage.fetchPriority = 'high';
const photoPreviewPlaceholder = document.querySelector('#photo-preview-placeholder');
const selectPreviewPhoto = document.querySelector('#select-preview-photo');
const previousPreview = document.querySelector('#preview-previous');
const nextPreview = document.querySelector('#preview-next');
const previewThumbnails = new Map();
let previewPhotos = [], previewIndex = -1;
let previewPhoto = null;
function previewThumbnail(photo) {
  const image = previewThumbnails.get(photo.id);
  if (image && image.complete && image.naturalWidth && image.naturalHeight) {
    try {
      const canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext('2d');
      if (context) {
        context.drawImage(image, 0, 0);
        return canvas.toDataURL('image/jpeg', 0.82);
      }
    } catch (_) { /* Fall back to the normal thumbnail request. */ }
  }
  return photo.url + '&thumb=1';
}
function updatePreviewSelection() {
  if (!previewPhoto) return;
  const selected = selectedPhotos.has(previewPhoto.id);
  selectPreviewPhoto.textContent = selected ? 'Quitar de la selección' : 'Seleccionar foto';
  selectPreviewPhoto.setAttribute('aria-pressed', String(selected));
}
function showPreviewAt(index) {
  if (index < 0 || index >= previewPhotos.length) return;
  previewIndex = index;
  previewPhoto = previewPhotos[index];
  previousPreview.disabled = index === 0;
  nextPreview.disabled = index === previewPhotos.length - 1;
  photoPreviewPlaceholder.src = previewThumbnail(previewPhoto);
  photoPreviewImage.classList.remove('is-ready');
  const fullUrl = savePhotoUrl(previewPhoto.url);
  photoPreviewImage.onload = () => {
    if (photoPreviewImage.getAttribute('src') === fullUrl) photoPreviewImage.classList.add('is-ready');
  };
  photoPreviewImage.src = fullUrl;
  updatePreviewSelection();
}
previousPreview.addEventListener('click', () => showPreviewAt(previewIndex - 1));
nextPreview.addEventListener('click', () => showPreviewAt(previewIndex + 1));
photoPreview.addEventListener('keydown', event => {
  if (event.key === 'ArrowLeft') { event.preventDefault(); showPreviewAt(previewIndex - 1); }
  if (event.key === 'ArrowRight') { event.preventDefault(); showPreviewAt(previewIndex + 1); }
});
selectPreviewPhoto.addEventListener('click', () => {
  if (!previewPhoto) return;
  if (selectedPhotos.has(previewPhoto.id)) selectedPhotos.delete(previewPhoto.id);
  else selectedPhotos.set(previewPhoto.id, previewPhoto.url);
  updateSelection();
  updatePreviewSelection();
});
document.querySelector('#close-photo-preview').addEventListener('click', () => photoPreview.close());
photoPreview.addEventListener('close', () => {
  photoPreviewImage.removeAttribute('src');
  photoPreviewPlaceholder.removeAttribute('src');
  photoPreviewImage.classList.remove('is-ready');
  previewPhoto = null;
  previewIndex = -1;
});
const grid = (element, photos) => {
  element.replaceChildren();
  for (const photo of photos) {
    const card = document.createElement('article');
    card.className = 'photo-card';
    const selectArea = document.createElement('label');
    selectArea.className = 'photo-select';
    const image = document.createElement('img');
    image.src = photo.url + '&thumb=1';
    image.alt = 'Recuerdo de la boda';
    image.loading = 'lazy';
    image.decoding = 'async';
    image.fetchPriority = 'low';
    previewThumbnails.set(photo.id, image);
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
    selectArea.append(image, selectLabel);
    const previewButton = document.createElement('button');
    previewButton.type = 'button';
    previewButton.className = 'preview-photo';
    previewButton.textContent = 'Ver foto';
    previewButton.setAttribute('aria-label', `Ver foto ${photo.name}`);
    previewButton.addEventListener('click', () => {
      const index = previewPhotos.findIndex(item => item.id === photo.id);
      if (index < 0) return;
      showPreviewAt(index);
      photoPreview.showModal();
    });
    card.append(selectArea, previewButton);
    element.append(card);
  }
};
updateSelection();
if (document.querySelector('#gallery-empty')) {
const galleryGroups = ['desayuno-color', 'desayuno-bn', 'iglesia-color', 'iglesia-bn', 'banquete-color', 'banquete-bn', 'baile-color'];
fetch('/api/gallery').then(r => { if (!r.ok) throw new Error(); return r.json(); }).then(photos => {
  previewThumbnails.clear();
  previewPhotos = galleryGroups.flatMap(group => photos.filter(photo => photo.category === group));
  for (const group of galleryGroups) {
    const entries = photos.filter(photo => photo.category === group);
    grid(document.querySelector(`#gallery-${group}`), entries);
    document.querySelector(`#group-${group}`).hidden = entries.length === 0;
  }
  for (const moment of ['desayuno', 'iglesia', 'banquete', 'baile']) {
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
    previewThumbnails.clear();
    previewPhotos = data;
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
    if (window.matchMedia('(max-width: 700px)').matches) {
      requestAnimationFrame(() => status.scrollIntoView({behavior: 'smooth', block: 'start'}));
    }
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
