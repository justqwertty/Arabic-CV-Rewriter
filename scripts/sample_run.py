"""
Run every case in samples/test-inputs.md through the model and write the results
to samples/last-run.md for native-speaker review.

    python scripts/sample_run.py                 # all cases, all three registers
    python scripts/sample_run.py --register tech # one register
    python scripts/sample_run.py --case 6        # one case

Foundry Local must be running with the model loaded. A 7B model on one GPU takes
roughly 10-30 seconds per call, so a full sweep (7 cases x 3 registers) is a
coffee-length wait, not an instant one.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prompt_loader  # noqa: E402
import server  # noqa: E402
from foundry_client import FoundryUnavailable  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUTS = os.path.join(ROOT, "samples", "test-inputs.md")
RESULTS = os.path.join(ROOT, "samples", "last-run.md")

CASE = re.compile(r"^## (\d+)\.\s*(.+?)$", re.MULTILINE)
BLOCK = re.compile(r"```\n(.*?)\n```", re.DOTALL)


def load_cases() -> list[tuple[int, str, str]]:
    with open(INPUTS, encoding="utf-8") as fh:
        text = fh.read()

    cases = []
    headings = list(CASE.finditer(text))
    for i, match in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[match.start():end]
        block = BLOCK.search(body)
        if block:
            cases.append((int(match.group(1)), match.group(2).strip(), block.group(1).strip()))
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", choices=prompt_loader.REGISTERS)
    parser.add_argument("--case", type=int)
    parser.add_argument("--output", default="ar", choices=prompt_loader.OUTPUTS)
    args = parser.parse_args()

    registers = [args.register] if args.register else list(prompt_loader.REGISTERS)
    cases = load_cases()
    if args.case:
        cases = [c for c in cases if c[0] == args.case]
    if not cases:
        print("No cases matched.")
        return 1

    lines = [
        "# Sample run",
        "",
        f"Generated {time.strftime('%Y-%m-%d %H:%M')} - output mode `{args.output}`.",
        "",
        "This file is overwritten on every run. See samples/test-inputs.md for",
        "what to look for in each case.",
        "",
    ]

    total = len(cases) * len(registers)
    done = 0

    for number, title, text in cases:
        lines += [f"## {number}. {title}", "", "**Input**", "", "```", text, "```", ""]
        for register in registers:
            done += 1
            print(f"[{done}/{total}] case {number} / {register} ...", flush=True)
            started = time.time()
            try:
                prompt = prompt_loader.build(register, args.output)
                result = server.chat(prompt, text)
            except FoundryUnavailable as exc:
                print(f"\n{exc}")
                return 1
            except Exception as exc:  # noqa: BLE001
                result = f"(failed: {exc})"
            elapsed = time.time() - started

            lines += [
                f"**{register}** _({elapsed:.0f}s)_",
                "",
                "```",
                result,
                "```",
                "",
            ]
        lines.append("---")
        lines.append("")

    with open(RESULTS, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"\nWrote {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
