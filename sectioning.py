"""Turns raw CV text into named sections, and keeps each section within the
per-call character limit that /api/rewrite enforces.

Two independent concerns live here:
  - parsing/validating the model's JSON sectioning response (parse_sections,
    fallback_section)
  - bin-packing an oversized section into several under-limit parts
    (split_oversized) - pure string logic, no model call involved.
"""
from __future__ import annotations

import json


class SectioningError(RuntimeError):
    """The model's sectioning response could not be parsed or validated."""


def parse_sections(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SectioningError(f"Model did not return valid JSON: {exc}") from exc

    if not isinstance(data, dict) or "sections" not in data:
        raise SectioningError("Model JSON is missing a 'sections' key.")

    sections = data["sections"]
    if not isinstance(sections, list) or not sections:
        raise SectioningError("Model 'sections' must be a non-empty list.")

    cleaned: list[dict] = []
    for i, section in enumerate(sections):
        if not isinstance(section, dict):
            raise SectioningError(f"Section {i} is not an object.")

        name = section.get("name")
        bullets = section.get("bullets")

        if not isinstance(name, str) or not name.strip():
            raise SectioningError(f"Section {i} is missing a valid 'name'.")
        if not isinstance(bullets, list) or not bullets or not all(
            isinstance(b, str) for b in bullets
        ):
            raise SectioningError(f"Section {i} is missing a valid 'bullets' list.")

        cleaned_bullets = [b.strip() for b in bullets if b.strip()]
        if not cleaned_bullets:
            raise SectioningError(f"Section {i} has no non-empty bullets.")

        cleaned.append({"name": name.strip(), "bullets": cleaned_bullets})

    return cleaned


def fallback_section(raw_text: str) -> list[dict]:
    """Used when the model's sectioning response can't be parsed even after a
    retry - one big section beats a guessed split."""
    return [{"name": "Full text", "bullets": [raw_text]}]


def _joined_len(bullets: list[str]) -> int:
    return len("\n".join(bullets))


def split_oversized(sections: list[dict], max_chars: int) -> list[dict]:
    """Bin-pack any section whose bullets (joined with '\\n') exceed
    max_chars into consecutive '<name> (i/total)' parts. Never splits a
    single bullet - one bullet alone over the limit becomes its own
    oversized part rather than being cut mid-fact."""
    output: list[dict] = []

    for section in sections:
        bullets = section["bullets"]
        if _joined_len(bullets) <= max_chars:
            output.append(section)
            continue

        chunks: list[list[str]] = []
        current: list[str] = []
        for bullet in bullets:
            candidate = current + [bullet]
            if current and _joined_len(candidate) > max_chars:
                chunks.append(current)
                current = [bullet]
            else:
                current = candidate
        if current:
            chunks.append(current)

        total = len(chunks)
        for idx, chunk in enumerate(chunks, start=1):
            name = f"{section['name']} ({idx}/{total})" if total > 1 else section["name"]
            output.append({"name": name, "bullets": chunk})

    return output
