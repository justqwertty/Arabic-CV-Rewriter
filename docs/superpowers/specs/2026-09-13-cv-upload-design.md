# CV Upload (PDF/DOCX) with Per-Section Rewrite — Design

**Status:** Approved by Omar, 2026-09-13
**Supersedes:** SPEC.md §4 non-goals ("No PDF export or file upload", "No multi-page CV parsing") — this is a deliberate scope expansion beyond the original 5-day v1, not an oversight.

## 1. Goal

Let a user upload a `.pdf` or `.docx` CV instead of pasting bullets by hand. The
backend extracts the text, asks the model to split it into named sections
(Experience, Education, Skills, ...), and the frontend shows an editable
review screen where the user can adjust section text and pick a register per
section before rewriting. Rewriting itself reuses the existing
`/api/rewrite` endpoint unchanged — one call per section.

The existing paste-a-textarea flow is untouched and remains the default.
Upload is an additional entry point, not a replacement.

## 2. Architecture

```
Upload (.pdf/.docx)
   │
   ▼
POST /api/parse-upload  (multipart, one file field)
   │
   ├─ extract.py: extract_text(file) -> raw_text        (pypdf / python-docx)
   │
   └─ sectioning model call (prompts/section-prompt.md)
        -> { "sections": [ { "name": str, "bullets": [str, ...] }, ... ] }
   │
   ▼
Frontend review screen
   - one editable card per section (name + bullets textarea + register <select>)
   - "Rewrite all sections" button
   │
   ▼
N × POST /api/rewrite   (existing endpoint, one call per section, unchanged)
   │
   ▼
Existing original/Arabic/English result cards, repeated per section
```

Nothing about `/api/rewrite`, `prompt_loader.py`, or `prompts/rewrite-prompt.md`
changes. The upload path only produces input text that flows into the same
pipeline that already handles pasted text.

## 3. Backend components

### `extract.py` (new)

```python
def extract_text(file_storage) -> str
```

- `.pdf` → `pypdf.PdfReader`, join page text with `\n\n`.
- `.docx` → `python-docx`, join paragraph text with `\n`.
- Raises `ExtractionError(message)` for: unsupported extension, corrupt/unreadable
  file, password-protected PDF, or extraction producing empty/whitespace-only text.
- No OCR, no layout/table awareness — text-layer extraction only. A scanned
  (image-only) PDF will raise `ExtractionError` via the empty-text check, and
  the error message says so explicitly rather than returning nothing.

### `prompts/section-prompt.md` (new)

Same convention as `prompts/rewrite-prompt.md` — isolated, re-read on every
request, no Python string buried in `server.py`. Single `## BASE` block
instructing the model to return **only** JSON of the shape
`{"sections": [{"name": "...", "bullets": ["...", ...]}]}`, splitting on
whatever section structure is actually present in the input (headings, blank
lines, obvious topic shifts). Names should be short and in the input's
dominant language (don't translate "الخبرات" to "Experience").

### `prompt_loader.py`

Add `build_section_prompt() -> str` that reads `section-prompt.md` the same
way `build()` reads `rewrite-prompt.md` — no register/output blocks needed,
it's a single fixed prompt.

### `POST /api/parse-upload`

- Accepts multipart form data, one file field (`file`).
- Extension allowlist: `.pdf`, `.docx` only (case-insensitive). Anything else → 400.
- **No whole-document character cap.** Extraction and sectioning run on
  whatever text comes out of the file — a real CV is the whole point of this
  endpoint, and an artificial ceiling would reject exactly the input it
  exists to handle. The existing `chat()` empty-response guard already
  produces a clear "exceeded the model's context window" error if a
  pathologically large document overflows Qwen's context — no new cap needed
  to catch that case, it reuses infrastructure that's already there.
- Calls the model with `build_section_prompt()` + raw text, same `chat()`
  helper and same timeout/connection-error handling already in `server.py`.
- Parses the model's JSON response. On `json.JSONDecodeError` or a shape
  mismatch (missing `sections` key, non-list, etc.), retries the model call
  once with the same input. If the retry also fails, falls back to a single
  synthetic section: `{"name": "Full text", "bullets": [raw_text]}` — a
  visibly degraded result (one big section instead of several) rather than a
  guessed split, consistent with `split_languages`'s existing philosophy of
  "a visible one-sided failure beats a silent mangling."
- **Oversized-section splitting.** `MAX_CHARS` (3,000) is still the limit
  `/api/rewrite` enforces per call. After sectioning (model-derived or
  fallback), run `split_oversized(sections) -> sections`: for any section
  whose bullets joined exceed `MAX_CHARS`, greedily bin-pack its bullets into
  consecutive chunks that each stay under the limit — never splitting a
  bullet itself, since a fact must not be cut mid-sentence — and rename the
  resulting parts `"<name> (1/3)"`, `"<name> (2/3)"`, etc. This is pure
  string bin-packing in Python, no extra model call. The rare case of a
  single bullet alone exceeding `MAX_CHARS` is left as-is; it will surface
  the existing `/api/rewrite` 413 on just that one card when the user tries
  to rewrite it, same message as today's paste flow.
- Response: `{"sections": [...], "source_filename": "..."}` — already
  post-split, so the frontend treats every entry as an ordinary independent
  section and needs no sub-card or re-merge logic.

## 4. Frontend

- A toggle above the input panel: **Paste text** (existing textarea, default)
  / **Upload CV** (new). Switching hides one and shows the other; only one
  input mode is active per rewrite session.
- Upload mode: a file input (`accept=".pdf,.docx"`) + an "Extract" button.
  While `/api/parse-upload` is in flight, reuse the existing spinner/busy
  pattern from the rewrite button.
- On success, render a review list below: one card per section, each with:
  - The section name as an editable text field (model-derived names can be
    wrong or too granular).
  - The bullets as an editable `<textarea>` (plain text, one bullet per
    line) — the user can fix bad splits or bad OCR-adjacent artifacts by hand
    before rewriting.
  - A register `<select>` (Formal / Corporate / Tech) defaulting to whatever
    is currently checked in the existing global register radio group.
  - Its own "Rewrite this section" button.
  - A page-level "Rewrite all sections" button that fires the same
    per-section call for every section in sequence (not parallel — a single
    7B model instance serializes requests anyway, and sequential keeps
    progress legible: each card flips to its own loading state and fills in
    as its response lands).
- Each section's result reuses the exact existing original/Arabic/English
  card markup and Copy-button logic from the paste flow — this is templated
  once and instantiated per section, not duplicated by hand.
- Output-language selector (Ar/En/Both) stays global, same as today — only
  register is per-section. (Rationale: mixing Arabic-only and English-only
  results across sections of one CV read as broken; mixing registers across
  sections — e.g. Skills in Tech register, Experience in Corporate — is a
  real and requested use case.)

## 5. Error handling

Follows the existing `server.py` convention: typed exception → specific HTTP
status → plain-language, non-technical message. New cases:

| Condition | Status | Message tone |
|---|---|---|
| Extension not `.pdf`/`.docx` | 400 | "Upload a PDF or Word (.docx) file." |
| Corrupt file / password-protected PDF | 422 | "Could not read that file — ..." specific reason where extract.py knows it. |
| Extraction yields empty text (e.g. scanned image PDF) | 422 | "No selectable text found in that file — this looks like a scanned image, which isn't supported yet." |
| Document too large for the model's context window | 502 | Existing `chat()` empty-response message, reused verbatim: suggests fewer bullets/a shorter document. |
| Sectioning JSON unparseable after retry | 200 (degraded) | Frontend shows a small inline notice: "Couldn't detect sections — showing the whole document as one block." above the single fallback section. |
| One section still over 3,000 chars after auto-split (single oversized bullet) | 413, but only on that one card | Same message `/api/rewrite` already returns today, shown inline on that section's card instead of blocking the whole upload. |
| Foundry unavailable / timeout during sectioning | 503 / 504 | Same messages already used by `/api/rewrite`, reused verbatim. |

## 6. Testing

- Unit tests for `extract.py`: one fixture each for a clean `.pdf`, a clean
  `.docx`, a corrupt file, and an empty file — assert correct text or the
  correct `ExtractionError` message.
- Unit test for the sectioning fallback path with the model call mocked to
  return malformed JSON — assert the synthetic single-section fallback.
- Unit tests for `split_oversized()`: a section under the limit passes
  through unchanged; a section over the limit splits into correctly-named
  `(n/total)` parts each under `MAX_CHARS`; a single bullet alone over the
  limit is left as one oversized part rather than crashing.
- Manual verification against a live Foundry Local instance: upload a real
  CV (Omar's own, or a sample), confirm sections are reasonable, confirm
  per-section register override actually changes output, confirm the
  degraded-fallback path by temporarily feeding the model unparseable input.
- No automated test of Arabic output *quality* for the sectioning path,
  consistent with the existing project convention (`sample_run.py` covers
  rewrite-prompt quality; sectioning is a structural JSON task, not a
  register/tone task, so quality review here means "are the boundaries
  sane," which is a manual, eyeball check).

## 7. Out of scope (still, even after this change)

- OCR / scanned-PDF support.
- Saving/persisting uploaded files or extracted sections (still stateless,
  per SPEC.md §2).
- Multi-file / batch upload (one file per parse-upload call).
- Reordering or merging sections in the UI (only edit-in-place and
  per-section register).
