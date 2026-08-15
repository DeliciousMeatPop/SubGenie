#!/usr/bin/env bash
# ============================================================================
#  SubGenie launcher for macOS.
#
#  Double-click in Finder to run setup/help. To process a movie, either drop a
#  file onto this .command in a terminal, or (easier) run from Terminal:
#      ./SubGenie.command "/path/to/Movie (2014).mkv"
#
#  You may need to allow it once: right-click -> Open, or
#      chmod +x SubGenie.command
#
#  Requires Python 3 (python.org, Homebrew `brew install python`, or Xcode CLT).
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    PY=python
fi

"$PY" "$SCRIPT_DIR/../run.py" "$@"
