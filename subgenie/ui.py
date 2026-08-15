"""Small, dependency-free terminal helpers for prompts and pretty output.

Kept separate from ``cli`` so the prompt logic is easy to reason about and so
non-interactive runs (mode=never) never import anything heavy. Everything
degrades gracefully when stdin isn't a TTY: prompts fall back to their default.
"""

from __future__ import annotations

import sys
from typing import Optional, Sequence

from .languages import Language, all_languages


def _supports_color() -> bool:
    return sys.stdout.isatty() and sys.platform != "win32"


def style(text: str, code: str) -> str:
    if not _supports_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def bold(text: str) -> str:
    return style(text, "1")


def dim(text: str) -> str:
    return style(text, "2")


def green(text: str) -> str:
    return style(text, "32")


def yellow(text: str) -> str:
    return style(text, "33")


def red(text: str) -> str:
    return style(text, "31")


def cyan(text: str) -> str:
    return style(text, "36")


def banner() -> str:
    return bold(cyan("SubGenie")) + dim("  –  subtitles, handled.")


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def confirm(prompt: str, default: bool = True) -> bool:
    """Yes/no prompt. Returns ``default`` when non-interactive."""
    if not is_interactive():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    while True:
        answer = input(prompt + suffix).strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print(dim("  Please answer y or n."))


def choose(prompt: str, options: Sequence[tuple[str, str]], default_index: int = 0) -> str:
    """Single-choice menu. ``options`` is a list of (value, label). Returns value.

    Falls back to the default option when non-interactive.
    """
    if not is_interactive():
        return options[default_index][0]
    print(prompt)
    for idx, (_, label) in enumerate(options, start=1):
        marker = "*" if idx - 1 == default_index else " "
        print(f"  {marker} {idx}) {label}")
    while True:
        raw = input(f"Choice [1-{len(options)}, default {default_index + 1}]: ").strip()
        if not raw:
            return options[default_index][0]
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        print(dim("  Enter a number from the list."))


def select_languages(default: Sequence[Language]) -> list[Language]:
    """Interactive language picker.

    Accepts a comma/space separated list of codes or names, ``all`` for every
    language, or blank to accept the defaults. Unknown tokens are reported and
    ignored. Shows the catalogue so users can pick and choose.
    """
    from .languages import resolve_many

    if not is_interactive():
        return list(default)

    print(bold("\nAvailable languages") + dim("  (code – name)"))
    catalogue = all_languages()
    # Two-column layout.
    half = (len(catalogue) + 1) // 2
    for i in range(half):
        left = catalogue[i]
        right = catalogue[i + half] if i + half < len(catalogue) else None
        left_str = f"  {left.sidecar_code:<3} {left.name}"
        if right:
            print(f"{left_str:<34}{right.sidecar_code:<3} {right.name}")
        else:
            print(left_str)

    default_codes = ", ".join(l.sidecar_code for l in default)
    print()
    print(dim("Enter codes/names separated by commas, 'all' for everything,"))
    print(dim(f"or press Enter for your default ({default_codes})."))
    while True:
        raw = input("Languages: ").strip()
        if not raw:
            return list(default)
        tokens = [t for chunk in raw.split(",") for t in chunk.split()]
        found, unknown = resolve_many(tokens)
        if unknown:
            print(yellow("  Unknown: ") + ", ".join(unknown))
        if found:
            print(green("  Selected: ") + ", ".join(l.name for l in found))
            return found
        print(dim("  Nothing recognized – try again, or Enter for the default."))
