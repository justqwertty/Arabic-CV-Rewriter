# Gulf-Market Arabic CV Rewriter

Paste rough CV bullet points — English, formal Arabic, Egyptian dialect, or all three in the same line — and get back the formally registered Modern Standard Arabic a Gulf recruiter expects, alongside the original. Everything runs locally: the model sits on your own GPU through Microsoft Foundry Local, so no CV text leaves the machine and there is no API bill.

## How It Works

1. **Paste your bullets.** One CV section at a time, up to 3,000 characters. Mixed input is fine — the tool sorts out the languages itself, you don't have to separate them first.
2. **Pick a target register.** *Formal* for government bodies and banks, *Corporate* for multinationals, *Tech* for startups and engineering teams. The register changes how conservative the Arabic is and how much English vocabulary survives untranslated.
3. **Pick an output language.** Arabic, English, or both side by side.
4. **Hit Rewrite.** The backend assembles a system prompt from `prompts/rewrite-prompt.md`, combining the base rules, the selected register block, the output-format block, and the few-shot examples, then sends it with your text to the local model.
5. **Read the result against the original.** Original and rewrite sit side by side so you can confirm nothing was invented. Each output pane has its own Copy button.

The rewrite converts dialect into MSA by meaning rather than word-for-word, uses the masdar (verbal-noun) construction Gulf CVs conventionally take, keeps every fact — numbers, dates, employers, tools — exactly as you wrote it, and returns bullet points rather than prose.

## Setup

Requires Python 3.10+ and a GPU with roughly 8 GB of headroom for a 7B model. Built and tested on an RTX 5050 / 32 GB RAM.

### 1. Install and start Foundry Local

Install Foundry Local from Microsoft, then load the model:

```bash
foundry run qwen2.5-coder-7b
```

Confirm the service is up and the model is loaded:

```bash
foundry server status     # older releases: foundry service status
foundry model list --loaded
```

The service picks its own port, which changes between runs. You do not need to note it — the backend resolves the endpoint at runtime (see *Libraries* below).

### 2. Install the backend

```bash
git clone <this repo>
cd Arabic-CV-Rewriter

python -m venv .venv
.venv\Scripts\activate         # Windows
source .venv/bin/activate      # macOS / Linux

pip install -r requirements.txt
```

### 3. Check the model is reachable

```bash
python foundry_client.py
```

Prints the resolved endpoint, the exact model id, and which resolution method found it. If this fails, the server will start anyway but every rewrite will return the same error — fix it here first.

### 4. Run

```bash
python server.py
```

Open <http://127.0.0.1:5000>. The banner under the title confirms which model answered.

### Reviewing prompt quality

```bash
python scripts/sample_run.py
```

Runs every case in `samples/test-inputs.md` through all three registers and writes `samples/last-run.md` for review. `samples/test-inputs.md` lists what to look for — invented facts first, register separation second. Prompt iteration happens entirely in `prompts/rewrite-prompt.md`, which is re-read on every request: edit, save, reload the browser. No restart.

### Deployment

There is no deployment step. The tool is designed to run on the machine that holds the model — that is the point of using Foundry Local rather than a cloud API. "Running it" means starting two things in order: `foundry run qwen2.5-coder-7b`, then `python server.py`.

## Libraries / Dependencies

| Package | Why |
|---|---|
| **Flask** | The backend is two stateless endpoints. An async framework would add setup cost for no benefit at this size. |
| **openai** | Foundry Local speaks the OpenAI HTTP protocol, so the official client works unchanged — only `base_url` points at localhost. This is also what makes swapping models a one-line change. |
| **foundry-local-sdk** | Resolves the service endpoint and api_key at runtime. Foundry Local binds a different port on each machine and after each restart, so hardcoding `localhost:<port>` works exactly once. `foundry_client.py` falls back to parsing the `foundry` CLI and then to probing known ports, so a failed SDK install is not fatal. |

No frontend framework, no build step, no database — the tool is text in, text out, with nothing to persist between requests.

### A note on the model

This was built against **Qwen 2.5 Coder 7B**, which was already installed. Qwen 2.5 Coder is code-specialised, not Arabic-tuned, and it shows: it needs a more explicit, example-heavy prompt to hold a register than a general-purpose model would, and it tends toward markdown fences and "Here is the rewrite:" preambles, which `server.py` strips rather than merely forbidding.

If output quality stays weak after prompt iteration, swapping in a general-purpose model is the documented fallback:

```bash
foundry run qwen2.5-7b-instruct
set FOUNDRY_MODEL_ALIAS=qwen2.5-7b-instruct     # Windows
export FOUNDRY_MODEL_ALIAS=qwen2.5-7b-instruct  # macOS / Linux
```

Because the interface is OpenAI-compatible, that is the entire change — no code edit, no rewrite.

## Possible Improvements

- **PDF and DOCX upload.** Paste-only is the honest v1 scope, but parsing an uploaded CV and rewriting section by section is the obvious next step and the one users will ask for first.
- **More Gulf registers.** Saudi public sector, UAE semi-government and Qatari energy-sector CVs are not interchangeable; each could get its own register block in `prompts/rewrite-prompt.md` without touching any code.
- **Batch processing.** A whole CV's worth of sections in one pass, with per-section registers, rather than one paste at a time.
- **A diff view.** Highlighting exactly which facts carried through and which words changed would make the fact-preservation guarantee visible instead of something the user has to verify by eye.
- **More dialects in the few-shot examples.** The examples currently lean Egyptian. Levantine, Gulf and Maghrebi input all reach the same MSA target but travel a different distance to get there.

## Why This Project

Most Arabic speakers write CVs either in English or in a dialect-inflected register that quietly signals the wrong thing to a Gulf recruiter, and no mainstream tool handles that gap — the register problem is invisible to anything trained primarily on English CVs. Building it locally, against a model running on my own hardware, is deliberate: Arabic-market AI tooling frequently has to work without sending personal documents to a foreign cloud API, and this is a working demonstration that it can.
