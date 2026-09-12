'use strict';

const $ = (id) => document.getElementById(id);

const input = $('input');
const goBtn = $('go');
const btnLabel = goBtn.querySelector('.btn-label');
const counter = $('counter');
const statusEl = $('status');
const errorEl = $('error');
const results = $('results');

let MAX_CHARS = 3000;
let busy = false;

const checked = (name) =>
  document.querySelector(`input[name="${name}"]:checked`).value;

/* --- health ------------------------------------------------------------ */

async function checkHealth() {
  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    if (data.ok) {
      statusEl.textContent = `Model ready — ${data.model}`;
      statusEl.className = 'status ok';
      if (data.max_chars) {
        MAX_CHARS = data.max_chars;
        input.maxLength = MAX_CHARS + 200;
        updateCounter();
      }
    } else {
      statusEl.textContent = data.error;
      statusEl.className = 'status bad';
    }
  } catch {
    statusEl.textContent = 'Backend not reachable. Is server.py running?';
    statusEl.className = 'status bad';
  }
}

/* --- input state ------------------------------------------------------- */

// First strong directional character decides which way the textarea reads, so
// Arabic input is not typed right-to-left inside a left-aligned box.
const FIRST_STRONG = /[A-Za-z؀-ۿݐ-ݿ]/;

function updateDirection() {
  const match = input.value.match(FIRST_STRONG);
  if (!match) {
    input.dir = 'auto';
    return;
  }
  input.dir = /[؀-ۿݐ-ݿ]/.test(match[0]) ? 'rtl' : 'ltr';
}

function updateCounter() {
  const length = input.value.length;
  counter.textContent = `${length.toLocaleString()} / ${MAX_CHARS.toLocaleString()}`;
  counter.classList.toggle('over', length > MAX_CHARS);
  goBtn.disabled = busy || length === 0 || length > MAX_CHARS;
}

input.addEventListener('input', () => {
  updateCounter();
  updateDirection();
});

/* --- rewrite ----------------------------------------------------------- */

function setBusy(state) {
  busy = state;
  goBtn.classList.toggle('loading', state);
  btnLabel.textContent = state ? 'Rewriting…' : 'Rewrite';
  updateCounter();
}

async function rewrite() {
  const text = input.value.trim();

  if (!text) {
    showError('Paste some bullet points first.');
    return;
  }
  if (text.length > MAX_CHARS) {
    showError(
      `That is ${text.length.toLocaleString()} characters. The limit is ` +
      `${MAX_CHARS.toLocaleString()} — rewrite one CV section at a time.`
    );
    return;
  }

  errorEl.hidden = true;
  setBusy(true);

  try {
    const res = await fetch('/api/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        register: checked('register'),
        output: checked('output')
      })
    });

    let data;
    try {
      data = await res.json();
    } catch {
      showError(`The server returned an unreadable response (${res.status}).`);
      return;
    }

    if (!res.ok) {
      showError(data.error || `Request failed (${res.status}).`);
      return;
    }

    if (!data.arabic && !data.english) {
      showError('The model returned nothing usable. Try again, or shorten the input.');
      return;
    }

    render(data);
  } catch (err) {
    showError(
      'Could not reach the backend. Check that server.py is still running. ' +
      `(${err.message})`
    );
  } finally {
    setBusy(false);
  }
}

function render(data) {
  $('out-original').textContent = data.original;
  $('out-arabic').textContent = data.arabic;
  $('out-english').textContent = data.english;

  $('card-ar').hidden = !data.arabic;
  $('card-en').hidden = !data.english;
  results.hidden = false;
  results.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
  errorEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/* --- copy -------------------------------------------------------------- */

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  // http://localhost is a secure context in every current browser, but a
  // machine reached over the LAN is not - fall back rather than fail.
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
}

document.querySelectorAll('.copy').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const text = $(btn.dataset.target).textContent;
    if (!text) return;
    try {
      await copyText(text);
      btn.textContent = 'Copied';
      btn.classList.add('done');
      setTimeout(() => {
        btn.textContent = 'Copy';
        btn.classList.remove('done');
      }, 1500);
    } catch {
      showError('Could not copy to clipboard — select the text and copy manually.');
    }
  });
});

/* --- go ---------------------------------------------------------------- */

goBtn.addEventListener('click', rewrite);

// Ctrl/Cmd + Enter from the textarea
input.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !goBtn.disabled) {
    rewrite();
  }
});

updateCounter();
checkHealth();
