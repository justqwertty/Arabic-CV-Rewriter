'use strict';

// Note: app.js (loaded before this script) already declares a top-level
// `const $` helper. Classic (non-module) <script> tags share one global
// lexical scope, so redeclaring `$` here would throw a SyntaxError and
// silently break this entire file. Use a distinct name instead.
const byId = (id) => document.getElementById(id);

const modePasteBtn = byId('mode-paste');
const modeUploadBtn = byId('mode-upload');
const pastePanel = byId('paste-panel');
const uploadPanel = byId('upload-panel');

const uploadFile = byId('upload-file');
const uploadExtractBtn = byId('upload-extract');
const uploadErrorEl = byId('upload-error');
const uploadDegradedEl = byId('upload-degraded');

const sectionsReview = byId('sections-review');
const sectionsList = byId('sections-list');
const rewriteAllBtn = byId('rewrite-all');
const sectionTemplate = byId('section-template');

const goBtn = byId('go');
const pasteErrorEl = byId('error');

const checkedGlobal = (name) =>
  document.querySelector(`input[name="${name}"]:checked`).value;

/* --- mode toggle --------------------------------------------------------- */

function setMode(mode) {
  const isUpload = mode === 'upload';
  modeUploadBtn.classList.toggle('active', isUpload);
  modePasteBtn.classList.toggle('active', !isUpload);
  modeUploadBtn.setAttribute('aria-selected', String(isUpload));
  modePasteBtn.setAttribute('aria-selected', String(!isUpload));
  uploadPanel.hidden = !isUpload;
  pastePanel.hidden = isUpload;
  goBtn.hidden = isUpload;
  pasteErrorEl.hidden = isUpload;
}

modePasteBtn.addEventListener('click', () => setMode('paste'));
modeUploadBtn.addEventListener('click', () => setMode('upload'));

/* --- extract -------------------------------------------------------------- */

function setExtractBusy(state) {
  uploadExtractBtn.classList.toggle('loading', state);
  uploadExtractBtn.disabled = state;
}

function showUploadError(message) {
  uploadErrorEl.textContent = message;
  uploadErrorEl.hidden = false;
}

async function extractSections() {
  const file = uploadFile.files[0];
  if (!file) {
    showUploadError('Choose a PDF or Word (.docx) file first.');
    return;
  }

  uploadErrorEl.hidden = true;
  uploadDegradedEl.hidden = true;
  sectionsReview.hidden = true;
  sectionsList.innerHTML = '';
  setExtractBusy(true);

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/parse-upload', { method: 'POST', body: formData });

    let data;
    try {
      data = await res.json();
    } catch {
      showUploadError(`The server returned an unreadable response (${res.status}).`);
      return;
    }

    if (!res.ok) {
      showUploadError(data.error || `Request failed (${res.status}).`);
      return;
    }

    uploadDegradedEl.hidden = !data.degraded;
    renderSections(data.sections);
  } catch (err) {
    showUploadError(`Could not reach the backend. (${err.message})`);
  } finally {
    setExtractBusy(false);
  }
}

uploadExtractBtn.addEventListener('click', extractSections);

/* --- section rendering ---------------------------------------------------- */

function renderSections(sections) {
  sectionsList.innerHTML = '';
  sections.forEach((section) => sectionsList.appendChild(buildSectionCard(section)));
  sectionsReview.hidden = sections.length === 0;
  sectionsReview.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function buildSectionCard(section) {
  const node = sectionTemplate.content.cloneNode(true);
  const card = node.querySelector('.section-card');

  const nameInput = card.querySelector('.section-name');
  const bulletsArea = card.querySelector('.section-bullets');
  const registerSelect = card.querySelector('.section-register');
  const rewriteBtn = card.querySelector('.section-rewrite');
  const errorEl = card.querySelector('.section-error');
  const resultsEl = card.querySelector('.section-results');

  nameInput.value = section.name;
  bulletsArea.value = section.bullets.join('\n');
  registerSelect.value = checkedGlobal('register');

  rewriteBtn.addEventListener('click', () => rewriteSection(card));

  return card;
}

async function rewriteSection(card) {
  const bulletsArea = card.querySelector('.section-bullets');
  const registerSelect = card.querySelector('.section-register');
  const rewriteBtn = card.querySelector('.section-rewrite');
  const errorEl = card.querySelector('.section-error');
  const resultsEl = card.querySelector('.section-results');

  const text = bulletsArea.value.trim();
  errorEl.hidden = true;

  if (!text) {
    errorEl.textContent = 'This section has no text to rewrite.';
    errorEl.hidden = false;
    return;
  }

  rewriteBtn.classList.add('loading');
  rewriteBtn.disabled = true;

  try {
    const res = await fetch('/api/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        register: registerSelect.value,
        output: checkedGlobal('output'),
      }),
    });

    let data;
    try {
      data = await res.json();
    } catch {
      errorEl.textContent = `The server returned an unreadable response (${res.status}).`;
      errorEl.hidden = false;
      return;
    }

    if (!res.ok) {
      errorEl.textContent = data.error || `Request failed (${res.status}).`;
      errorEl.hidden = false;
      return;
    }

    renderSectionResult(card, data);
  } catch (err) {
    errorEl.textContent = `Could not reach the backend. (${err.message})`;
    errorEl.hidden = false;
  } finally {
    rewriteBtn.classList.remove('loading');
    rewriteBtn.disabled = false;
  }
}

function renderSectionResult(card, data) {
  card.querySelector('.section-out-original').textContent = data.original;
  card.querySelector('.section-out-arabic').textContent = data.arabic;
  card.querySelector('.section-out-english').textContent = data.english;

  card.querySelector('.section-card-ar').hidden = !data.arabic;
  card.querySelector('.section-card-en').hidden = !data.english;
  card.querySelector('.section-results').hidden = false;
}

/* --- rewrite all ------------------------------------------------------------ */

async function rewriteAllSections() {
  rewriteAllBtn.classList.add('loading');
  rewriteAllBtn.disabled = true;

  const cards = Array.from(sectionsList.querySelectorAll('.section-card'));
  for (const card of cards) {
    await rewriteSection(card);
  }

  rewriteAllBtn.classList.remove('loading');
  rewriteAllBtn.disabled = false;
}

rewriteAllBtn.addEventListener('click', rewriteAllSections);

/* --- copy (per-section result cards) ---------------------------------------- */

async function copySectionText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
}

sectionsList.addEventListener('click', async (e) => {
  const btn = e.target.closest('.copy');
  if (!btn) return;

  const card = btn.closest('.section-card');
  const targetClass = btn.dataset.role === 'copy-ar' ? '.section-out-arabic' : '.section-out-english';
  const text = card.querySelector(targetClass).textContent;
  if (!text) return;

  try {
    await copySectionText(text);
    btn.textContent = 'Copied';
    btn.classList.add('done');
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('done');
    }, 1500);
  } catch {
    /* Clipboard failures are surfaced by the browser's own permission UI;
       nothing actionable to add here. */
  }
});
