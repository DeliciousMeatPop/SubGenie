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


def _extract_section(lines: list[str], label: str) -> str:
    """Return the body under a ``## [label]`` / ``## label`` heading, trimmed.

    Captures everything up to the next ``## `` heading or the trailing block of
    reference-style link definitions (``[0.1.0]: https://...``) that Keep a
    Changelog keeps at the bottom of the file.
    """
    escaped = re.escape(label)
    start_re = re.compile(rf"^##\s+\[?{escaped}\]?\b", re.IGNORECASE)
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
    return "\n".join(section).strip()


def _looks_empty(section: str) -> bool:
    """True when a section has no real content.

    Sub-headings (``### Added``), an italic "nothing yet" placeholder, and HTML
    comments don't count as content - a section made only of those is empty.
    """
    if not section:
        return True
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Drop a leading list marker so "- _Nothing yet._" is seen as italic.
        content = re.sub(r"^[-*+]\s*", "", stripped)
        if content.startswith(("#", "_", "<!--")):
            continue
        return False  # found a real line
    return True


def extract_changelog(version: str) -> str:
    """Pull the notes for ``version`` out of CHANGELOG.md.

    Resolution order:
      1. An explicit ``## [<version>]`` section (the ideal - you moved the notes
         under a version heading before tagging).
      2. Otherwise the ``## [Unreleased]`` section, so notes you kept there still
         land in the release. This is what makes the common workflow "just work"
         without hand-editing the changelog at tag time.
      3. A helpful placeholder if both are empty/missing.
    """
    try:
        with open(CHANGELOG, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return _FALLBACK_CHANGELOG

    lines = text.splitlines()

    exact = _extract_section(lines, version)
    if not _looks_empty(exact):
        return exact

    unreleased = _extract_section(lines, "Unreleased")
    if not _looks_empty(unreleased):
        return unreleased

    return _FALLBACK_CHANGELOG


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
