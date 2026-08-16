#!/usr/bin/env python3
"""Promote the ``[Unreleased]`` changelog section into a dated version section.

At release time this turns:

    ## [Unreleased]
    ### Added
    - shiny new thing

into:

    ## [Unreleased]

    _Nothing yet…_

    ## [0.0.3] - 2026-08-16
    ### Added
    - shiny new thing

so each release's notes contain **only that release's** changes, instead of
everything accumulated in Unreleased since the first release. It also fixes up
the reference-style links at the bottom.

Idempotent: if a section for the version already exists, or Unreleased has no
real content, nothing changes. Prints whether it changed anything so a workflow
can decide whether to commit.

Usage:
    python scripts/promote_changelog.py 0.0.3
    python scripts/promote_changelog.py v0.0.3 --date 2026-08-16   # pin date (tests)
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
REPO_URL = "https://github.com/DeliciousMeatPop/SubGenie"
PLACEHOLDER = (
    "_Nothing yet — new entries go here and are moved under a version heading "
    "automatically at release time._"
)

_HEADING = re.compile(r"^##\s+")
_REF_DEF = re.compile(r"^\[[^\]]+\]:\s+\S")


def _section_exists(lines: list[str], version: str) -> bool:
    pat = re.compile(rf"^##\s+\[?{re.escape(version)}\]?\b")
    return any(pat.match(line) for line in lines)


def _find_unreleased(lines: list[str]) -> int | None:
    pat = re.compile(r"^##\s+\[?Unreleased\]?\b", re.IGNORECASE)
    for i, line in enumerate(lines):
        if pat.match(line):
            return i
    return None


def _has_meaningful(body_lines: list[str]) -> bool:
    """True if there's real content (not just sub-headings / placeholder)."""
    for line in body_lines:
        stripped = line.strip()
        if not stripped:
            continue
        content = re.sub(r"^[-*+]\s*", "", stripped)
        if content.startswith(("#", "_", "<!--")):
            continue
        return True
    return False


def _update_refs(text: str, version: str) -> str:
    """Point the [Unreleased] compare link at the new tag and add the tag link."""
    lines = text.splitlines()
    already = any(re.match(rf"^\[{re.escape(version)}\]:\s", l) for l in lines)
    out: list[str] = []
    for line in lines:
        if re.match(r"^\[Unreleased\]:\s", line, re.IGNORECASE):
            out.append(f"[Unreleased]: {REPO_URL}/compare/v{version}...HEAD")
            if not already:
                out.append(f"[{version}]: {REPO_URL}/releases/tag/v{version}")
                already = True
            continue
        out.append(line)
    return "\n".join(out)


def promote(text: str, version: str, date: str) -> tuple[str, bool]:
    """Return (new_text, changed)."""
    version = version.strip().lstrip("vV")
    lines = text.splitlines()

    if _section_exists(lines, version):
        return text, False

    start = _find_unreleased(lines)
    if start is None:
        return text, False

    end = len(lines)
    for j in range(start + 1, len(lines)):
        if _HEADING.match(lines[j]) or _REF_DEF.match(lines[j]):
            end = j
            break

    body = lines[start + 1:end]
    if not _has_meaningful(body):
        return text, False

    # Trim blank lines around the captured body.
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()

    new_block = [
        lines[start],          # "## [Unreleased]"
        "",
        PLACEHOLDER,
        "",
        f"## [{version}] - {date}",
        "",
        *body,
        "",
    ]
    new_text = "\n".join(lines[:start] + new_block + lines[end:])
    new_text = _update_refs(new_text, version)
    if not new_text.endswith("\n"):
        new_text += "\n"
    return new_text, True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("version")
    parser.add_argument("--date", default=None, help="ISO date (defaults to today)")
    args = parser.parse_args(argv[1:])

    date = args.date or datetime.date.today().isoformat()
    text = CHANGELOG.read_text(encoding="utf-8")
    new_text, changed = promote(text, args.version, date)
    if changed:
        CHANGELOG.write_text(new_text, encoding="utf-8")
        print(f"Promoted [Unreleased] -> [{args.version.lstrip('vV')}] - {date}")
    else:
        print("No changelog promotion needed (already promoted or nothing new).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
