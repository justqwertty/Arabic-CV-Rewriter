'use strict';

const $ = (id) => document.getElementById(id);

const input = $('input');
const goBtn = $('go');
const statusEl = $('status');
const errorEl = $('error');
const results = $('results');

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
    } else {
      statusEl.textContent = data.error;
      statusEl.className = 'status bad';
    }
  } catch (err) {
    statusEl.textContent = 'Backend not reachable. Is server.py running?';
    statusEl.className = 'status bad';
  }
}

/* --- rewrite ----------------------------------------------------------- */

async function rewrite() {
  const text = input.value.trim();
  if (!text) return;

  errorEl.hidden = true;
  goBtn.disabled = true;
  goBtn.textContent = 'Rewriting…';

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
    const data = await res.json();

    if (!res.ok) {
      show(data.error || `Request failed (${res.status}).`);
      return;
    }
    render(data);
  } catch (err) {
    show(err.message);
  } finally {
    goBtn.disabled = false;
    goBtn.textContent = 'Rewrite';
  }
}

function render(data) {
  $('out-original').textContent = data.original;
  $('out-arabic').textContent = data.arabic;
  $('out-english').textContent = data.english;

  $('card-ar').hidden = !data.arabic;
  $('card-en').hidden = !data.english;
  results.hidden = false;
  results.dataset.mode = data.output_mode;
}

function show(message) {
  errorEl.textContent = message;
  errorEl.hidden = false;
}

/* --- copy -------------------------------------------------------------- */

document.querySelectorAll('.copy').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const text = $(btn.dataset.target).textContent;
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      const original = btn.textContent;
      btn.textContent = 'Copied';
      setTimeout(() => { btn.textContent = original; }, 1500);
    } catch (err) {
      show('Could not copy to clipboard.');
    }
  });
});

goBtn.addEventListener('click', rewrite);
checkHealth();
