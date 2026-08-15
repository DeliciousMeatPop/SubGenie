#!/usr/bin/env python3
"""Assemble the body for a GitHub release from templates + CHANGELOG.md.

Used by the release workflow, but runnable locally to preview what a release
will look like:

    python scripts/build_release_notes.py v0.1.0

Resolution order for the body:
  1. If ``.github/release-notes/<tag>.md`` exists, use it verbatim (this is how
     a special release - e.g. the very first one - overrides the default).
  2. Otherwise use ``.github/RELEASE_TEMPLATE.md``.

Either way, these placeholders are then substituted:
  * ``{{VERSION}}``   -> version without the leading ``v`` (e.g. 0.2.0)
  * ``{{TAG}}``       -> the full tag (e.g. v0.2.0)
  * ``{{CHANGELOG}}`` -> the matching section pulled from CHANGELOG.md, so the
                         "what changed" list sits near the top of every release.

Keeping the changelog in one file (CHANGELOG.md) and injecting the relevant
slice means each release's notes always say what changed without anyone
copy-pasting.
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, ".github", "RELEASE_TEMPLATE.md")
NOTES_DIR = os.path.join(ROOT, ".github", "release-notes")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")

_FALLBACK_CHANGELOG = (
    "_No CHANGELOG entry found for this version yet. "
    "Add one under this heading in `CHANGELOG.md`, or edit this draft._"
)


def normalize(tag: str) -> tuple[str, str]:
    """Return (tag, version) from whatever the caller passed."""
    tag = tag.strip()
    if not tag:
        raise SystemExit("A tag/version argument is required, e.g. v0.1.0")
    if not tag.startswith("v"):
        tag = "v" + tag
    version = tag[1:]
    return tag, version


def extract_changelog(version: str) -> str:
    """Pull the section for ``version`` out of CHANGELOG.md.

    Matches a heading like ``## [0.2.0] - 2026-08-15`` or ``## 0.2.0`` and
    returns everything up to the next ``## `` heading, trimmed. Falls back to a
    helpful placeholder when there's no match.
    """
    try:
        with open(CHANGELOG, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return _FALLBACK_CHANGELOG

    lines = text.splitlines()
    escaped = re.escape(version)
    # Heading for this version: '## [0.2.0]...' or '## 0.2.0...'
    start_re = re.compile(rf"^##\s+\[?{escaped}\]?\b")
    # Stop at the next '## ' heading, or at the trailing block of reference-style
    # link definitions (e.g. '[0.1.0]: https://...') that Keep a Changelog keeps
    # at the bottom of the file.
    ref_def_re = re.compile(r"^\[[^\]]+\]:\s+\S")
    section: list[str] = []
    capturing = False
    for line in lines:
        if capturing and (re.match(r"^##\s+", line) or ref_def_re.match(line)):
            break
        if capturing:
            section.append(line)
            continue
        if start_re.match(line):
            capturing = True
    body = "\n".join(section).strip()
    return body or _FALLBACK_CHANGELOG


def load_template(tag: str) -> str:
    per_release = os.path.join(NOTES_DIR, f"{tag}.md")
    if os.path.isfile(per_release):
        with open(per_release, "r", encoding="utf-8") as handle:
            return handle.read()
    with open(TEMPLATE, "r", encoding="utf-8") as handle:
        return handle.read()


def render(tag: str) -> str:
    tag, version = normalize(tag)
    template = load_template(tag)
    changelog = extract_changelog(version)
    return (
        template
        .replace("{{CHANGELOG}}", changelog)
        .replace("{{VERSION}}", version)
        .replace("{{TAG}}", tag)
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: build_release_notes.py <tag> [output-file]", file=sys.stderr)
        return 2
    body = render(argv[1])
    if len(argv) >= 3:
        with open(argv[2], "w", encoding="utf-8") as handle:
            handle.write(body)
    else:
        print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
