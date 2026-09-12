"""
Gulf-Market Arabic CV Rewriter - backend.

Day 3: the register and output-language choices made in the browser are now
wired through to the prompt, and "both" responses are split into two fields so
the frontend can lay them out side by side instead of showing one blob.
"""

from __future__ import annotations

import re

from flask import Flask, jsonify, request, send_from_directory
from openai import OpenAI

import foundry_client
import prompt_loader
from foundry_client import FoundryUnavailable
from prompt_loader import PromptError

app = Flask(__name__, static_folder="static", static_url_path="")

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
    arabic = len(ARABIC.findall(text))
    latin = len(re.findall(r"[A-Za-z]", text))
    return arabic > latin


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
    if is_arabic(first):
        return first, second
    return second, first


def chat(system_prompt: str, user_text: str) -> str:
    endpoint = foundry_client.resolve()
    client = OpenAI(base_url=endpoint.base_url, api_key=endpoint.api_key)

    completion = client.chat.completions.create(
        model=endpoint.model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0.25,
        max_tokens=2048,
    )
    return clean(completion.choices[0].message.content or "")


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
        }
    )


@app.post("/api/rewrite")
def rewrite():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    register = body.get("register") or prompt_loader.DEFAULT_REGISTER
    mode = body.get("output") or prompt_loader.DEFAULT_OUTPUT

    if not text:
        return jsonify({"error": "No text provided."}), 400

    try:
        system_prompt = prompt_loader.build(register, mode)
    except PromptError as exc:
        return jsonify({"error": str(exc)}), 500

    try:
        result = chat(system_prompt, text)
    except FoundryUnavailable as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Model call failed: {exc}"}), 502

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


if __name__ == "__main__":
    print("Checking Foundry Local...")
    try:
        ep = foundry_client.resolve()
        print(f"  endpoint: {ep.base_url}")
        print(f"  model:    {ep.model_id}  (via {ep.source})")
    except FoundryUnavailable as exc:
        print(f"  WARNING: {exc}")
        print("  Server will still start; /api/health will report the problem.")

    app.run(host="127.0.0.1", port=5000, debug=True)
