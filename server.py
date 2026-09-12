"""
Gulf-Market Arabic CV Rewriter - backend.

Day 1: prove the loop. Text arrives from the browser, goes to the local Qwen
model through Foundry Local's OpenAI-compatible API, and comes back. The prompt
here is deliberately a placeholder - the real register-aware prompt is Day 2's
job and lives in its own file so it can be edited without touching this server.
"""

from __future__ import annotations

from flask import Flask, jsonify, request, send_from_directory
from openai import OpenAI

import foundry_client
from foundry_client import FoundryUnavailable

# PLACEHOLDER - replaced on Day 2 by prompts/rewrite-prompt.md
PLACEHOLDER_PROMPT = (
    "You rewrite CV bullet points into formal Modern Standard Arabic suitable "
    "for Gulf employers. Return bullet points only, no commentary."
)

app = Flask(__name__, static_folder="static", static_url_path="")


def chat(system_prompt: str, user_text: str) -> str:
    endpoint = foundry_client.resolve()
    client = OpenAI(base_url=endpoint.base_url, api_key=endpoint.api_key)

    completion = client.chat.completions.create(
        model=endpoint.model_id,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0.3,
    )
    return completion.choices[0].message.content or ""


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/health")
def health():
    """Is Foundry Local up with a model loaded? Called on page load."""
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
    if not text:
        return jsonify({"error": "No text provided."}), 400

    try:
        output = chat(PLACEHOLDER_PROMPT, text)
    except FoundryUnavailable as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:  # noqa: BLE001 - surface the real error on Day 1
        return jsonify({"error": f"Model call failed: {exc}"}), 502

    return jsonify({"original": text, "output": output})


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
