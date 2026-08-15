#!/usr/bin/env bash
# ============================================================================
#  SubtitleGenie launcher for Linux.
#
#  Usage:
#      ./subtitlegenie.sh "/path/to/Movie (2014) 3D.mkv"
#      ./subtitlegenie.sh setup
#
#  On many desktops you can also drop files onto this script in the file
#  manager (mark it executable first: chmod +x subtitlegenie.sh).
#
#  Requires Python 3.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    PY=python
fi

exec "$PY" "$SCRIPT_DIR/../run.py" "$@"
