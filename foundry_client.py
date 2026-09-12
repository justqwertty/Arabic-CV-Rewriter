"""
Locating the Foundry Local service.

Foundry Local serves an OpenAI-compatible HTTP API on localhost, but the port is
assigned when the service starts and differs between machines and between runs.
Hardcoding ``localhost:<port>`` works once and then breaks, so this module
resolves the endpoint at runtime, trying sources in order of reliability:

  1. FOUNDRY_ENDPOINT env var    - explicit override, wins over everything else
  2. foundry-local-sdk (Python)  - the documented path. Two SDK generations ship
                                   incompatible APIs; both shapes are handled.
  3. `foundry server status`     - parses the service URL out of CLI output
  4. A short list of known ports - last resort so a missing SDK is not fatal

Whichever source wins, the result is confirmed by calling ``/models`` on it.
That round trip doubles as the "is the model actually loaded?" check and tells
us the exact id to send in chat requests, which is not the catalog alias:

    alias:  qwen2.5-coder-7b
    id:     qwen2.5-coder-7b-instruct-generic-gpu

Sending the alias where the id is expected returns a 404 from the service, which
is a confusing error to debug, hence resolving it properly here.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

# The model this project was built against. Override with FOUNDRY_MODEL_ALIAS to
# try a different local model - because the interface is OpenAI-compatible, that
# is the only change needed to swap models.
DEFAULT_ALIAS = os.environ.get("FOUNDRY_MODEL_ALIAS", "qwen2.5-coder-7b")

# Ports Foundry Local has been observed to bind. Only used if steps 1-3 fail.
KNOWN_PORTS = (55588, 5273, 5272, 8080)

PROBE_TIMEOUT = 3.0


class FoundryUnavailable(RuntimeError):
    """Raised when no running Foundry Local service could be found."""


@dataclass(frozen=True)
class Endpoint:
    base_url: str   # e.g. http://127.0.0.1:55588/v1
    api_key: str    # local placeholder; Foundry Local does not authenticate
    model_id: str   # exact id to pass as `model=` in chat requests
    source: str     # which resolution step won, for the /api/health readout


_cached: Optional[Endpoint] = None


# --------------------------------------------------------------------------
# probing
# --------------------------------------------------------------------------

def _normalise(url: str) -> str:
    """Return a base_url that ends in exactly one /v1."""
    url = url.strip().rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    return url


def _list_models(base_url: str) -> Optional[List[str]]:
    """GET {base_url}/models. Returns model ids, or None if nothing answers."""
    try:
        with urllib.request.urlopen(base_url + "/models", timeout=PROBE_TIMEOUT) as r:
            payload = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None

    data = payload.get("data", payload if isinstance(payload, list) else [])
    ids = [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
    return ids


def _pick_model(ids: List[str], alias: str) -> Optional[str]:
    """Match a catalog alias against the ids the service actually serves."""
    if not ids:
        return None

    alias_l = alias.lower()
    for model_id in ids:
        if alias_l in model_id.lower():
            return model_id

    # Alias not found verbatim - fall back to the same model family, then to
    # whatever is loaded, so a renamed variant still works.
    family = alias_l.split("-")[0]
    for model_id in ids:
        if family in model_id.lower():
            return model_id
    return ids[0]


# --------------------------------------------------------------------------
# resolution steps
# --------------------------------------------------------------------------

def _from_env() -> Optional[str]:
    url = os.environ.get("FOUNDRY_ENDPOINT")
    return _normalise(url) if url else None


def _from_sdk(alias: str) -> Optional[str]:
    """Ask the Foundry Local SDK. Handles both SDK generations."""
    # Generation 1 (foundry-local-sdk <= 0.5.x): manager exposes .endpoint
    try:
        from foundry_local import FoundryLocalManager  # type: ignore

        manager = FoundryLocalManager(alias)
        if getattr(manager, "endpoint", None):
            return _normalise(manager.endpoint)
    except Exception:
        pass

    # Generation 2: Configuration + initialize, service URL lives on the config
    try:
        from foundry_local_sdk import Configuration, FoundryLocalManager  # type: ignore

        FoundryLocalManager.initialize(Configuration(app_name="arabic-cv-rewriter"))
        manager = FoundryLocalManager.instance
        urls = getattr(getattr(manager, "config", None), "web", None) or {}
        url = urls.get("urls") if isinstance(urls, dict) else None
        if url:
            return _normalise(str(url).split(";")[0])
    except Exception:
        pass

    return None


def _from_cli() -> Optional[str]:
    """Parse the service URL out of the foundry CLI.

    Command name changed between releases (`service` -> `server`), so try both
    and take the first that prints a URL.
    """
    for args in (["foundry", "server", "status"], ["foundry", "service", "status"]):
        try:
            out = subprocess.run(
                args, capture_output=True, text=True, timeout=15, shell=False
            )
        except (OSError, subprocess.SubprocessError):
            continue

        text = (out.stdout or "") + (out.stderr or "")
        match = re.search(r"https?://[\w\.\-]+:\d+", text)
        if match:
            return _normalise(match.group(0))
    return None


def _from_known_ports() -> Optional[str]:
    for port in KNOWN_PORTS:
        base = f"http://127.0.0.1:{port}/v1"
        if _list_models(base) is not None:
            return base
    return None


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------

def resolve(alias: str = DEFAULT_ALIAS, refresh: bool = False) -> Endpoint:
    """Find a live Foundry Local service, or raise FoundryUnavailable."""
    global _cached
    if _cached is not None and not refresh:
        return _cached

    api_key = os.environ.get("FOUNDRY_API_KEY", "not-needed-for-local")
    attempts = (
        ("FOUNDRY_ENDPOINT", _from_env()),
        ("foundry-local-sdk", _from_sdk(alias)),
        ("foundry CLI", _from_cli()),
        ("known port", _from_known_ports()),
    )

    tried = []
    for source, base_url in attempts:
        if not base_url:
            continue
        tried.append(f"{source} -> {base_url}")

        ids = _list_models(base_url)
        if ids is None:
            continue  # nothing listening there

        model_id = _pick_model(ids, alias)
        if model_id is None:
            raise FoundryUnavailable(
                f"Foundry Local is running at {base_url} but has no model loaded. "
                f"Start one with:  foundry run {alias}"
            )

        _cached = Endpoint(base_url, api_key, model_id, source)
        return _cached

    detail = "; ".join(tried) if tried else "no endpoint found by any method"
    raise FoundryUnavailable(
        "Could not reach Foundry Local. Start the service and load the model:\n"
        f"    foundry run {alias}\n"
        "then confirm with:\n"
        "    foundry server status\n"
        f"(tried: {detail})"
    )


if __name__ == "__main__":
    # Standalone check: python foundry_client.py
    try:
        ep = resolve()
    except FoundryUnavailable as exc:
        raise SystemExit(f"[x] {exc}")
    print(f"[ok] endpoint : {ep.base_url}")
    print(f"[ok] model    : {ep.model_id}")
    print(f"[ok] found via: {ep.source}")
