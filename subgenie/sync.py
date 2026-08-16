"""Adjust subtitle timing — a fixed offset, or automatic audio alignment.

Two modes:

* **Manual offset** (``shift_srt``): add/subtract a fixed number of seconds from
  every timestamp. Pure Python, always available; handy when a subtitle is
  consistently early/late.

* **Automatic** (``autosync``): align the subtitle to the movie's *audio* using
  `ffsubsync <https://github.com/smacke/ffsubsync>`_. It detects speech in the
  audio and warps the subtitle to match, fixing both offset and framerate drift.
  ffsubsync is a separate ``pip`` tool (it isn't bundled), so this degrades to
  "unavailable" when it isn't installed, and the caller guides the user.

Hash-matched OpenSubtitles results are already synced to the exact release, so
sync mainly matters for title-matched / fallback subtitles.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from typing import Optional

_TIME = re.compile(r"(\d{1,2}):(\d{2}):(\d{2}),(\d{3})")


def _to_ms(h: str, m: str, s: str, ms: str) -> int:
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + int(ms)


def _to_timestamp(ms: int) -> str:
    ms = max(0, ms)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def shift_srt(srt_text: str, offset_seconds: float) -> str:
    """Shift every SRT timestamp by ``offset_seconds`` (may be negative)."""
    offset_ms = int(round(offset_seconds * 1000))
    if offset_ms == 0:
        return srt_text

    def repl(match: re.Match) -> str:
        return _to_timestamp(_to_ms(*match.groups()) + offset_ms)

    return _TIME.sub(repl, srt_text)


def autosync_available() -> bool:
    return shutil.which("ffsubsync") is not None


def install_hint() -> str:
    return (
        "Automatic sync needs 'ffsubsync' (a separate tool). Install it with:\n"
        "    pip install ffsubsync\n"
        "Then re-run with --sync. (Or use --sync-offset SECONDS for a fixed shift.)"
    )


def autosync(movie_path: str, srt_text: str, *, timeout: int = 600) -> Optional[str]:
    """Align ``srt_text`` to the movie's audio via ffsubsync.

    Returns the re-timed SRT text, or None if ffsubsync isn't installed or the
    alignment fails (so the caller can fall back to the original).
    """
    exe = shutil.which("ffsubsync")
    if not exe:
        return None
    tmpdir = tempfile.mkdtemp(prefix="subgenie_sync_")
    src = os.path.join(tmpdir, "in.srt")
    out = os.path.join(tmpdir, "out.srt")
    try:
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(srt_text)
        result = subprocess.run(
            [exe, movie_path, "-i", src, "-o", out],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        if result.returncode == 0 and os.path.isfile(out):
            with open(out, "r", encoding="utf-8", errors="replace") as handle:
                return handle.read()
        return None
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
