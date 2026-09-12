"""
Gulf-Market Arabic CV Rewriter - backend.

Day 2: the placeholder prompt is gone. The system prompt is assembled by
prompt_loader from prompts/rewrite-prompt.md, which is where all prompt
iteration happens - nothing about the wording lives in this file.
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


def clean(text: str) -> str:
    text = text.strip()
    fenced = FENCE.match(text)
    if fenced:
        text = fenced.group(1).strip()
    text = PREAMBLE.sub("", text).strip()
    return text


def chat(system_prompt: str, user_text: str) -> str:
    endpoint = foundry_client.resolve()
    client = OpenAI(base_url=endpoint.base_url, api_key=endpoint.api_key)

    completion = client.chat.completions.create(
        model=endpoint.model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        # Low but not zero: register-switching needs some room to choose
        # phrasing, while facts must not drift.
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
    output = body.get("output") or prompt_loader.DEFAULT_OUTPUT

    if not text:
        return jsonify({"error": "No text provided."}), 400

    try:
        system_prompt = prompt_loader.build(register, output)
    except PromptError as exc:
        return jsonify({"error": str(exc)}), 500

    try:
        result = chat(system_prompt, text)
    except FoundryUnavailable as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"Model call failed: {exc}"}), 502

    return jsonify(
        {
            "original": text,
            "output": result,
            "register": register,
            "output_mode": output,
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
