#!/usr/bin/env python3
"""Zero-install entry point.

You don't have to ``pip install`` SubtitleGenie to use it. This script lets you run
the tool straight from the source folder, and it's what the per-OS launchers
call. On Windows you can even drag a movie file directly onto this file.

    python run.py "My Movie (2014) 3D HSBS.mkv"
    python run.py                # no args -> prints help / setup tip
"""

import os
import sys

# Make sure the local package is importable when run from anywhere.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subgenie.cli import main  # noqa: E402

if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # e.g. piping output into `head`; exit quietly.
        try:
            sys.stdout.close()
        except Exception:
            pass
        sys.exit(0)
