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
import sys
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


def _ffmpeg_available() -> bool:
    from . import ffmpeg as ffmpeg_tools
    return ffmpeg_tools.ffmpeg_path() is not None


def _ffsubsync_available() -> bool:
    """True if ffsubsync can be used (bundled/importable, or on PATH)."""
    if shutil.which("ffsubsync"):
        return True
    try:
        import ffsubsync  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def autosync_available() -> bool:
    """Whether *any* auto-sync engine is available.

    True if ffsubsync is present, or if ffmpeg is (our built-in engine uses it).
    """
    return _ffsubsync_available() or _ffmpeg_available()


def install_hint() -> str:
    return (
        "Auto-align uses ffmpeg (built in). Install ffmpeg with "
        "'subtitlegenie install-ffmpeg' if you haven't. For the highest-quality "
        "alignment you can also install ffsubsync (pip install ffsubsync)."
    )


def autosync(movie_path: str, srt_text: str, *, timeout: int = 600, log=None) -> Optional[str]:
    """Align ``srt_text`` to the movie's audio.

    Tries ffsubsync first when available (best quality — fixes offset *and*
    framerate drift), then falls back to the built-in ffmpeg engine (fixes a
    constant offset). Returns the re-timed SRT, or None if nothing could align.
    """
    result = _ffsubsync(movie_path, srt_text, timeout=timeout)
    if result is not None:
        return result
    return builtin_autosync(movie_path, srt_text, log=log)


def _ffsubsync(movie_path: str, srt_text: str, *, timeout: int) -> Optional[str]:
    """Run ffsubsync via its CLI (on PATH or bundled). None if unavailable/failed."""
    exe = shutil.which("ffsubsync")
    if not exe and not _ffsubsync_available():
        return None
    tmpdir = tempfile.mkdtemp(prefix="subgenie_sync_")
    src = os.path.join(tmpdir, "in.srt")
    out = os.path.join(tmpdir, "out.srt")
    try:
        with open(src, "w", encoding="utf-8") as handle:
            handle.write(srt_text)
        cmd = [exe, movie_path, "-i", src, "-o", out] if exe else \
            [sys.executable, "-m", "ffsubsync", movie_path, "-i", src, "-o", out]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
        if result.returncode == 0 and os.path.isfile(out):
            with open(out, "r", encoding="utf-8", errors="replace") as handle:
                return handle.read()
        return None
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---- built-in ffmpeg auto-sync (constant offset) --------------------------

_SRT_TS = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")


def _srt_intervals(srt_text: str) -> list[tuple[float, float]]:
    """Return [(start_sec, end_sec), …] for each cue, sorted by start."""
    intervals: list[tuple[float, float]] = []
    for line in srt_text.replace("\r\n", "\n").split("\n"):
        if "-->" not in line:
            continue
        stamps = _SRT_TS.findall(line)
        if len(stamps) < 2:
            continue
        start = _stamp_seconds(stamps[0])
        end = _stamp_seconds(stamps[1])
        if end > start:
            intervals.append((start, end))
    intervals.sort()
    return intervals


def _stamp_seconds(groups) -> float:
    h, m, s, ms = groups
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000.0


def _speech_intervals(movie_path: str, log=None) -> Optional[list[tuple[float, float]]]:
    """Detect speech (non-silent) intervals in the movie's audio via ffmpeg."""
    from . import ffmpeg as ffmpeg_tools

    ffmpeg = ffmpeg_tools.ffmpeg_path()
    if not ffmpeg:
        return None
    if log:
        log("  Analyzing audio to align subtitles…")
    cmd = [
        ffmpeg, "-hide_banner", "-nostats", "-vn", "-i", movie_path,
        "-ac", "1", "-ar", "16000",
        "-af", "silencedetect=noise=-30dB:d=0.4", "-f", "null", "-",
    ]
    try:
        err = subprocess.run(
            cmd, capture_output=True, text=True, timeout=1800, check=False
        ).stderr
    except (OSError, subprocess.SubprocessError):
        return None

    silences: list[tuple[float, float]] = []
    start: Optional[float] = None
    total = 0.0
    for line in err.splitlines():
        m = re.search(r"silence_start:\s*(-?[\d.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = re.search(r"silence_end:\s*(-?[\d.]+)", line)
        if m:
            end = float(m.group(1))
            if start is not None and end > start:
                silences.append((start, end))
            total = max(total, end)
            start = None
    # Speech = the gaps between silences up to the movie's duration.
    duration = ffmpeg_tools_duration(movie_path) or (total if total else None)
    if not duration:
        return None
    speech: list[tuple[float, float]] = []
    cursor = 0.0
    for s0, s1 in silences:
        if s0 > cursor:
            speech.append((cursor, min(s0, duration)))
        cursor = max(cursor, s1)
    if cursor < duration:
        speech.append((cursor, duration))
    return [iv for iv in speech if iv[1] > iv[0]]


def ffmpeg_tools_duration(movie_path: str) -> Optional[float]:
    from . import ffmpeg as ffmpeg_tools
    probe = ffmpeg_tools.ffprobe_path()
    if not probe:
        return None
    cmd = [probe, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=nw=1:nk=1", movie_path]
    try:
        return float(subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _total_overlap(a: list, b: list) -> float:
    """Total overlapping duration between two sorted interval lists."""
    i = j = 0
    total = 0.0
    while i < len(a) and j < len(b):
        lo = max(a[i][0], b[j][0])
        hi = min(a[i][1], b[j][1])
        if hi > lo:
            total += hi - lo
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def _best_lag(speech: list, subs: list, max_lag: float, coarse: float, fine: float) -> tuple[float, float]:
    """Search for the lag (seconds) that best aligns subs onto speech."""
    def score(lag: float) -> float:
        shifted = [(s + lag, e + lag) for s, e in subs]
        return _total_overlap(speech, shifted)

    best_lag, best = 0.0, -1.0
    steps = int((2 * max_lag) / coarse) + 1
    for k in range(steps):
        lag = -max_lag + k * coarse
        val = score(lag)
        if val > best:
            best, best_lag = val, lag
    # Refine around the coarse best.
    k = -int(coarse / fine)
    while k <= int(coarse / fine):
        lag = best_lag + k * fine
        val = score(lag)
        if val > best:
            best, refined = val, lag
            best_lag = refined
        k += 1
    return best_lag, best


def builtin_autosync(movie_path: str, srt_text: str, *, log=None) -> Optional[str]:
    """Align a subtitle by finding the constant offset that best matches speech.

    Uses only ffmpeg (silencedetect) plus a small pure-Python cross-correlation,
    so it works in the standalone build with no extra dependencies. Fixes a
    constant offset (the common desync); it does not correct framerate drift.
    """
    subs = _srt_intervals(srt_text)
    if not subs:
        return None
    speech = _speech_intervals(movie_path, log=log)
    if not speech:
        return None

    lag, best = _best_lag(speech, subs, max_lag=120.0, coarse=0.5, fine=0.1)
    if best <= 0:
        return None                 # no overlap at any lag → can't align
    if abs(lag) < 0.1:
        return srt_text             # already aligned; nothing to change
    if log:
        log(f"  Built-in sync: shifting {lag:+.2f}s")
    return shift_srt(srt_text, lag)
