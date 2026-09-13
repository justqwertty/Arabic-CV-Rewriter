"""
Assembles the system prompt from prompts/rewrite-prompt.md.

The prompt is kept in markdown rather than in a Python string so it can be
edited and reviewed by someone who does not read Python - which matters here,
because the person who has to judge the Arabic is not the person who wrote the
server. The file is re-read on every request, so editing it and reloading the
browser is the whole iteration loop: no restart, no redeploy.
"""

from __future__ import annotations

import os
import re
from typing import Dict

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "rewrite-prompt.md")
SECTION_PROMPT_PATH = os.path.join(
    os.path.dirname(__file__), "prompts", "section-prompt.md"
)

REGISTERS = ("formal", "corporate", "tech")
OUTPUTS = ("ar", "en", "both")

DEFAULT_REGISTER = "corporate"
DEFAULT_OUTPUT = "both"


class PromptError(RuntimeError):
    """The prompt file is missing or has lost a block the server needs."""


def _parse(text: str) -> Dict[str, str]:
    """Split the markdown into {heading: body}, dropping HTML comments."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    blocks: Dict[str, str] = {}
    current = None
    buffer: list[str] = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                blocks[current] = "\n".join(buffer).strip()
            current = line[3:].strip().upper()
            buffer = []
        elif current:
            buffer.append(line)

    if current:
        blocks[current] = "\n".join(buffer).strip()
    return blocks


def build(register: str = DEFAULT_REGISTER, output: str = DEFAULT_OUTPUT) -> str:
    """Return the full system prompt for one rewrite request."""
    if register not in REGISTERS:
        register = DEFAULT_REGISTER
    if output not in OUTPUTS:
        output = DEFAULT_OUTPUT

    try:
        with open(PROMPT_PATH, encoding="utf-8") as fh:
            blocks = _parse(fh.read())
    except OSError as exc:
        raise PromptError(f"Could not read {PROMPT_PATH}: {exc}") from exc

    needed = ["BASE", f"REGISTER: {register.upper()}", f"OUTPUT: {output.upper()}"]
    missing = [key for key in needed if key not in blocks]
    if missing:
        raise PromptError(
            f"prompts/rewrite-prompt.md is missing block(s): {', '.join(missing)}"
        )

    parts = [blocks["BASE"]]
    parts.append("REGISTER FOR THIS REQUEST\n\n" + blocks[needed[1]])
    parts.append("OUTPUT FORMAT FOR THIS REQUEST\n\n" + blocks[needed[2]])
    if blocks.get("EXAMPLES"):
        parts.append("EXAMPLES\n\n" + blocks["EXAMPLES"])
        # The examples cover all three registers, so whichever one is closest
        # in shape to the actual input tends to win by recency, regardless of
        # which register was asked for. Restating the selected register last
        # counteracts that pull without duplicating any example content.
        parts.append("REGISTER FOR THIS REQUEST, AGAIN\n\n" + blocks[needed[1]])

    # Sections are joined with blank lines, not a `---` rule: in "both" mode
    # `---` is the separator the model is told to emit between the Arabic and
    # English blocks, and seeing it used as section furniture in its own
    # instructions is a reliable way to get it sprinkled through the output.
    return "\n\n\n".join(parts)


def build_section_prompt() -> str:
    """Return the fixed system prompt used to split raw CV text into named
    sections. Unlike build(), there is no register/output variation - one
    prompt, re-read from disk on every request like the rewrite prompt."""
    try:
        with open(SECTION_PROMPT_PATH, encoding="utf-8") as fh:
            blocks = _parse(fh.read())
    except OSError as exc:
        raise PromptError(f"Could not read {SECTION_PROMPT_PATH}: {exc}") from exc

    if "BASE" not in blocks:
        raise PromptError("prompts/section-prompt.md is missing block: BASE")
    return blocks["BASE"]


if __name__ == "__main__":
    print(build())
