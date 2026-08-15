#!/usr/bin/env python3
"""Stamp a version into ``subgenie/__init__.py``.

Used by the release workflow so the built binary's ``__version__`` (and thus
``--version`` and the self-update check) matches the release it was built from.

This lives in a file, invoked as ``python scripts/stamp_version.py <version>``,
specifically so there is no Python source on the shell command line. An earlier
inline ``python -c "...re.sub(r'...[^\"]*'...)"`` broke on Windows runners,
where the default shell is PowerShell and read ``[^"]`` as an array-index
expression. Passing only a plain version string as an argument is safe in every
shell.

Usage:
    python scripts/stamp_version.py 0.0.3
    python scripts/stamp_version.py v0.0.3   # a leading 'v' is stripped
"""

from __future__ import annotations

import pathlib
import re
import sys

INIT = pathlib.Path(__file__).resolve().parent.parent / "subgenie" / "__init__.py"


def main(argv: list[str]) -> int:
    if len(argv) < 2 or not argv[1].strip():
        print("usage: stamp_version.py <version>", file=sys.stderr)
        return 2

    version = argv[1].strip().lstrip("vV")
    text = INIT.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r'__version__ = "[^"]*"',
        f'__version__ = "{version}"',
        text,
    )
    if count == 0:
        print("error: __version__ assignment not found in subgenie/__init__.py",
              file=sys.stderr)
        return 1
    INIT.write_text(new_text, encoding="utf-8")
    print(f"Stamped __version__ = {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
