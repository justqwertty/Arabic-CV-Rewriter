# Gulf-Market Arabic CV Rewriter — working context

Local web tool: rough CV bullets (Arabic / English / Egyptian dialect / mixed)
in, Gulf-recruiter-appropriate formal MSA out. Runs entirely on this machine
against Qwen 2.5 Coder 7B through Microsoft Foundry Local.

Full original spec: `.staging/SPEC.md`. Read it before changing scope — it
defines the non-goals and the five-commit plan, both of which are deliberate.
(Those non-goals were later deliberately superseded once — see the CV-upload
feature below, which has its own design doc.)

## If you're an AI agent picking this project up

This section exists so you don't have to re-derive the last session's
findings from scratch. Read it before touching code.

**Two live checkouts may exist on this machine at once**, and this bit
everyone in the last session:
- The main checkout (wherever `git status` shows branch `main`).
- A git worktree at `.claude/worktrees/<name>/` — each worktree has its own
  `.venv`, and each can run its own `python server.py` bound to
  `127.0.0.1:5000`. Two `server.py` instances (one per checkout) can end up
  both listening on port 5000 at once on Windows without either erroring, and
  whichever bound first silently answers every request — so a browser can
  show stale content from the *other* checkout with no visible error. If a
  page looks wrong or a feature seems missing after you just edited code,
  before debugging the code: `netstat -ano | grep ':5000'` (or the
  PowerShell equivalent) and check every PID's actual command line
  (`Get-CimInstance Win32_Process -Filter "ProcessId=<pid>" | Select
  CommandLine`) — don't assume the server you started is the one answering.
- Always run `server.py` and `pytest` with the checkout's *own* `.venv`
  (`.venv/Scripts/python.exe`, not a bare `python`/system Python), and always
  confirm which directory you're actually in before starting a server —
  `pwd`/`git rev-parse --show-toplevel` first.

**Classic `<script>` tags share ONE global scope — this has caused two real
outages already.** `static/app.js` and `static/upload.js` both load as plain
(non-module) `<script>` tags in `index.html`, which means every top-level
`const`/`let`/`function` name in either file lives in the same global lexical
environment. A duplicate top-level name in the second-loaded script throws a
page-wide `SyntaxError` that silently kills that entire file before any of
its code runs — no console-visible crash a casual glance would catch, just a
page where every button in the second script's UI does nothing.
This happened twice in the same session: once with a shared `$` helper name,
then again with `goBtn` after a fix reintroduced it. **Before adding any new
top-level identifier to `static/upload.js` (or any future script tag loaded
alongside `app.js`), grep both files for that name first**, or check with:
```bash
grep -oE '^(const|let|function) [A-Za-z0-9_$]+' static/app.js static/upload.js | awk -F: '{print $2}' | sort | uniq -d
```
An empty result means no collision.

**Where things stand as of 2026-09-13:** the original 5-day build (below)
is done and its base loop (`foundry_client.py` resolving the endpoint,
`server.py` serving, the model answering) was reconfirmed working. On top of
that, a **CV upload (PDF/DOCX) with per-section rewrite** feature was
designed and implemented via the brainstorming → writing-plans →
subagent-driven-development workflow, on branch `worktree-cv-upload`
(pushed to `origin`, not yet merged — check `git log --oneline main..origin/worktree-cv-upload`
to see if that's still true). Its design doc and implementation plan are
checked in under `docs/superpowers/specs/` and `docs/superpowers/plans/` —
read those first if you're extending or debugging that feature; they contain
the actual reasoning (why no whole-document char cap, why sections are
bin-packed rather than rejected when oversized, etc.), which is cheaper to
read than to re-derive from the code. New backend modules from that feature:
`extract.py` (PDF/DOCX text extraction), `sectioning.py` (parse/fallback/
oversized-split logic), `prompts/section-prompt.md` — all covered by
`tests/` (`pytest tests/` from the feature branch's own `.venv`).

## State

Written, not yet verified against a running model. All five days exist as
overlays in `.staging/day1..day5`; `stage-commit.ps1` replays them into commits.

| Day | Deliverable | Status |
|---|---|---|
| 1 | End-to-end loop, endpoint resolution | written, model call unverified |
| 2 | Register-aware prompt + sample harness | written, **Arabic unreviewed** |
| 3 | Register + language selectors, side-by-side | written, UI verified in headless Chromium |
| 4 | Edge cases, errors, RTL, responsive | written, error paths unit-tested with the model stubbed |
| 5 | README | written |

**Nothing in this repo has been run against Foundry Local.** The previous
session had no shell on this machine. Every `foundry` command in the README is
unverified. Start there.

## Immediate next actions

1. `foundry server status` and `foundry model list --loaded` — confirm what is
   actually serving. Older releases use `foundry service status`.
2. `python foundry_client.py` — prints the resolved endpoint, the selected model
   id, and which of four resolution methods found it. If this fails, everything
   else fails identically.
3. Replay the commits: `.\stage-commit.ps1 -Day 1`, then 2..5. Or `-All`.
4. `python server.py`, open http://127.0.0.1:5000, paste a real bullet.
5. `python scripts/sample_run.py` → writes `samples/last-run.md`. **This is the
   actual Day 2 deliverable** — the prompt is a non-native first draft and the
   spec requires native-speaker review before Day 2 is called done.

## What to check in the Arabic (this is the real risk)

`samples/test-inputs.md` lists the failure modes per case. Priority order:

1. **Invented facts** — case 6 is deliberately vague ("عملت شغل كويس"). If the
   model returns a specific team size or metric, rule 1 of the prompt is not
   holding and nothing else matters until it does.
2. **Register collapse** — if `formal`, `corporate` and `tech` produce the same
   Arabic, the register blocks are too weak to steer a code-specialised model.
3. Masdar form (إدارة / تطوير) not first-person past (كنت مسؤولاً).
4. Western digits, not Arabic-Indic.
5. Tech register keeps `API`, `backend`, `React` in English; formal register
   leaks none.

If quality stays weak after prompt iteration, the documented fallback is
swapping to a general-purpose model — `FOUNDRY_MODEL_ALIAS=qwen2.5-7b-instruct`.
One env var, no code change. The README says so; keep that honest.

## Conventions

- **The prompt lives in `prompts/rewrite-prompt.md`, never in Python.** It is
  re-read on every request: edit, save, reload the browser. No restart. Blocks
  are `## BASE`, `## REGISTER: <name>`, `## OUTPUT: <ar|en|both>`, `## EXAMPLES`
  — renaming a heading requires updating `prompt_loader.py`.
- Sections are joined with blank lines, never `---`. In `both` mode `---` is the
  separator the model emits between Arabic and English; using it as section
  furniture in the prompt gets it sprinkled through the output.
- Frontend is vanilla HTML/CSS/JS. No framework, no build step. Keep it that way.
- Arabic output panes need `dir="rtl"` plus `unicode-bidi: plaintext` — the tech
  register produces Arabic sentences with inline English terms, and without
  plaintext bidi they get visually reordered.
- Commits stay scoped to one day each. The staged history is part of the
  deliverable; do not bundle days.

## Model variants — non-obvious

Foundry compiles one build per execution provider and serves each as its own id:

```
qwen2.5-coder-7b-instruct-trtrtx-gpu:2      TensorRT-RTX (this machine, RTX 5050)
qwen2.5-coder-7b-instruct-cuda-gpu          CUDA
qwen2.5-coder-7b-instruct-generic-gpu       DirectML / generic GPU
qwen2.5-coder-7b-instruct-generic-cpu       CPU
```

An alias matches several at once. `_pick_model` in `foundry_client.py` ranks
them (`EXECUTION_ORDER`) and takes the fastest; an exact id in
`FOUNDRY_MODEL_ALIAS` overrides the ranking. This ranking is **untested against
a live `/models` response** — if `python foundry_client.py` reports a `cpu`
build while the trtrtx one is loaded, the id parsing is wrong. Check it.

Foundry's port changes between runs, so it is resolved at runtime, never
hardcoded: env var → SDK (two incompatible generations, both handled) → parsing
`foundry server status` → probing known ports.

## Known rough edges

- Qwen 2.5 Coder is code-specialised. It reaches for markdown fences and "Here
  is the rewrite:" preambles regardless of instructions; `server.py` strips both
  rather than only forbidding them. Expect to extend those regexes.
- `split_languages` falls back to script detection when the model ignores the
  `---` separator, and deliberately shows a one-sided result rather than
  guessing a split point — a visible failure beats a silent mangling.
- `stage-commit.ps1` and `.staging/` are gitignored scaffolding. Delete both
  once the history is replayed.
- `CLAUDE.md` is now tracked (see the "If you're an AI agent" section above
  for why this file needs to survive across clones/branches). If you're
  reading this from a fresh clone and it's missing, someone re-gitignored it —
  check `.gitignore`.
- Static `<script>` tag name collisions: see "If you're an AI agent" above —
  this is the single most likely way a frontend change silently breaks
  everything else on the page.
