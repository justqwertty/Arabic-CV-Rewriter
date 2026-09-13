"""
Gulf-Market Arabic CV Rewriter - backend.

Day 4: nothing fails silently. Every path out of /api/rewrite returns either a
result or a sentence a non-technical user can act on, and a local 7B model's
slowest realistic response still fits inside the timeout.
"""

from __future__ import annotations

import os
import re

import openai
from flask import Flask, jsonify, request, send_from_directory
from openai import OpenAI
from werkzeug.utils import secure_filename

import extract
import foundry_client
import prompt_loader
import sectioning
from foundry_client import FoundryUnavailable
from prompt_loader import PromptError

app = Flask(__name__, static_folder="static", static_url_path="")

# Matches the counter in the browser. Not a billing limit - nothing is billed -
# but a 7B model's quality and latency both degrade on very long inputs, and a
# CV section that runs past 3,000 characters is not a CV section any more.
MAX_CHARS = 3000

# CV uploads accepted by /api/parse-upload. Anything else is rejected before
# extraction is even attempted.
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".docx"}

# A 7B model on a single consumer GPU can take well over a minute on a long
# input. Anything past this is a hung service rather than a slow one.
REQUEST_TIMEOUT = 180

# Qwen 2.5 Coder is a code model. Left alone it reaches for markdown fences and
# for "Here is the rewritten version:" preambles no matter how firmly the prompt
# forbids them, so the output is cleaned rather than merely requested.
FENCE = re.compile(r"^\s*```[\w-]*\s*\n(.*?)\n\s*```\s*$", re.DOTALL)
PREAMBLE = re.compile(
    r"^\s*(here (is|are)[^\n:]*:|sure[^\n]*:|الترجمة[^\n]*:|النص[^\n]*:)\s*\n",
    re.IGNORECASE,
)
SEPARATOR = re.compile(r"^\s*-{3,}\s*$", re.MULTILINE)

# Rough test for "does this line carry Arabic script". Used only to decide which
# half of a two-part response is which when the model emits them out of order.
ARABIC = re.compile(r"[؀-ۿ]")


def clean(text: str) -> str:
    text = text.strip()
    fenced = FENCE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    return PREAMBLE.sub("", text).strip()


def is_arabic(text: str) -> bool:
    """True if Arabic script dominates. Tech-register bullets are mixed, so a
    presence check is not enough - compare against Latin letters."""
    return len(ARABIC.findall(text)) > len(re.findall(r"[A-Za-z]", text))


def split_languages(text: str, mode: str) -> tuple[str, str]:
    """Return (arabic, english) for a response in the requested output mode."""
    if mode == "ar":
        return text, ""
    if mode == "en":
        return "", text

    parts = [p.strip() for p in SEPARATOR.split(text) if p.strip()]
    if len(parts) < 2:
        # The model ignored the separator. Rather than guessing a split point,
        # show the whole response in the pane its script belongs to - a visibly
        # one-sided result is easier to diagnose than a silently mangled one.
        return (text, "") if is_arabic(text) else ("", text)

    first, second = parts[0], parts[1]
    return (first, second) if is_arabic(first) else (second, first)


def chat(system_prompt: str, user_text: str) -> str:
    endpoint = foundry_client.resolve()
    client = OpenAI(
        base_url=endpoint.base_url,
        api_key=endpoint.api_key,
        timeout=REQUEST_TIMEOUT,
        max_retries=1,
    )

    completion = client.chat.completions.create(
        model=endpoint.model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0.1,
        max_tokens=2048,
    )

    choice = completion.choices[0]
    text = clean(choice.message.content or "")
    if not text:
        raise RuntimeError(
            "The model returned an empty response. This usually means the "
            "prompt plus your input exceeded its context window - try fewer "
            "bullets at a time."
        )
    return text


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/health")
def health():
    try:
        endpoint = foundry_client.resolve(refresh=True)
    except FoundryUnavailable as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503
    return jsonify(
        {
            "ok": True,
            "endpoint": endpoint.base_url,
            "model": endpoint.model_id,
            "resolved_via": endpoint.source,
            "max_chars": MAX_CHARS,
        }
    )


def chat_error_response(exc: Exception):
    """Map a chat()/Foundry error to a (JSON body, status) response. Shared
    between /api/rewrite and /api/parse-upload so both endpoints fail the
    same way for the same underlying problem."""
    if isinstance(exc, FoundryUnavailable):
        return jsonify({"error": str(exc)}), 503
    if isinstance(exc, openai.APITimeoutError):
        return jsonify(
            {
                "error": f"The model did not respond within {REQUEST_TIMEOUT} "
                "seconds. Check that Foundry Local is still running, then try a "
                "shorter input."
            }
        ), 504
    if isinstance(exc, openai.APIConnectionError):
        return jsonify(
            {
                "error": "Lost the connection to Foundry Local. Restart it with "
                "`foundry run qwen2.5-coder-7b` and reload this page."
            }
        ), 503
    if isinstance(exc, openai.NotFoundError):
        # Almost always a stale cached model id after a service restart.
        foundry_client.resolve(refresh=True)
        return jsonify(
            {"error": "The loaded model changed. Reload the page and try again."}
        ), 409
    return jsonify({"error": f"Rewrite failed: {exc}"}), 502


@app.post("/api/rewrite")
def rewrite():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    register = body.get("register") or prompt_loader.DEFAULT_REGISTER
    mode = body.get("output") or prompt_loader.DEFAULT_OUTPUT

    # --- input validation ---------------------------------------------
    if not text:
        return jsonify({"error": "Paste some bullet points first."}), 400

    if len(text) > MAX_CHARS:
        return jsonify(
            {
                "error": f"That is {len(text):,} characters. The limit is "
                f"{MAX_CHARS:,} — rewrite one CV section at a time for better "
                f"results anyway."
            }
        ), 413

    # --- prompt assembly ----------------------------------------------
    try:
        system_prompt = prompt_loader.build(register, mode)
    except PromptError as exc:
        return jsonify({"error": str(exc)}), 500

    # --- model call ----------------------------------------------------
    try:
        result = chat(system_prompt, text)
    except Exception as exc:  # noqa: BLE001
        return chat_error_response(exc)

    arabic, english = split_languages(result, mode)
    return jsonify(
        {
            "original": text,
            "arabic": arabic,
            "english": english,
            "register": register,
            "output_mode": mode,
        }
    )


def _run_sectioning(section_prompt: str, raw_text: str) -> tuple[list[dict], bool]:
    """Try the model's sectioning JSON up to twice; fall back to one big
    section rather than guessing a split. Returns (sections, degraded)."""
    for _ in range(2):
        raw_json = chat(section_prompt, raw_text)
        try:
            return sectioning.parse_sections(raw_json), False
        except sectioning.SectioningError:
            continue
    return sectioning.fallback_section(raw_text), True


@app.post("/api/parse-upload")
def parse_upload():
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"error": "Upload a PDF or Word (.docx) file."}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return jsonify({"error": "Upload a PDF or Word (.docx) file."}), 400

    file_bytes = file.read()

    try:
        raw_text = extract.extract_text(file_bytes, ext)
    except extract.ExtractionError as exc:
        return jsonify({"error": str(exc)}), 422

    try:
        section_prompt = prompt_loader.build_section_prompt()
    except PromptError as exc:
        return jsonify({"error": str(exc)}), 500

    try:
        sections, degraded = _run_sectioning(section_prompt, raw_text)
    except Exception as exc:  # noqa: BLE001
        return chat_error_response(exc)

    sections = sectioning.split_oversized(sections, MAX_CHARS)

    return jsonify(
        {
            "sections": sections,
            "source_filename": secure_filename(file.filename),
            "degraded": degraded,
        }
    )


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "No such endpoint."}), 404


if __name__ == "__main__":
    print("Checking Foundry Local...")
    try:
        ep = foundry_client.resolve()
        print(f"  endpoint: {ep.base_url}")
        print(f"  model:    {ep.model_id}  (via {ep.source})")
    except FoundryUnavailable as exc:
        print(f"  WARNING: {exc}")
        print("  Server will still start; /api/health will report the problem.")

    print("\n  http://127.0.0.1:5000\n")
    app.run(host="127.0.0.1", port=5000, debug=True)
