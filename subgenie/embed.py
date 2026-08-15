"""Mux subtitle files into a movie container using ffmpeg.

We copy all existing streams and add each subtitle as a new soft-subtitle track
with correct language metadata and a ``forced`` disposition where appropriate.
No video/audio re-encoding happens, so this is fast and lossless - it just
rewrites the container.

MKV and MP4 need different subtitle codecs (``srt`` vs ``mov_text``); we pick
based on the output extension. The result is written to a temp file in the same
directory and then atomically swapped over the original (optionally keeping a
backup), so an interrupted mux never corrupts the source file.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

from .languages import Language


@dataclass
class SubtitleTrack:
    path: str
    language: Language
    forced: bool = False
    hearing_impaired: bool = False


class EmbedError(Exception):
    """Raised when muxing can't be performed or fails."""


def ffmpeg_path() -> Optional[str]:
    return shutil.which("ffmpeg")


def ffprobe_path() -> Optional[str]:
    return shutil.which("ffprobe")


def ffmpeg_available() -> bool:
    return ffmpeg_path() is not None


def embedded_languages(movie_path: str) -> set[str]:
    """Return alpha3 language codes of subtitle tracks already inside the movie.

    Uses ffprobe when available; returns an empty set if ffprobe is missing so
    callers simply don't get to skip already-present languages (safe default).
    """
    probe = ffprobe_path()
    if not probe:
        return set()
    cmd = [
        probe, "-v", "error",
        "-select_streams", "s",
        "-show_entries", "stream_tags=language",
        "-of", "default=nw=1:nk=1",
        movie_path,
    ]
    try:
        output = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return {line.strip().lower() for line in output.splitlines() if line.strip()}


def _subtitle_codec(output_ext: str) -> str:
    ext = output_ext.lower()
    if ext in (".mp4", ".m4v", ".mov"):
        return "mov_text"
    return "srt"


def embed_subtitles(
    movie_path: str,
    tracks: list[SubtitleTrack],
    *,
    keep_original: bool = False,
) -> str:
    """Mux ``tracks`` into ``movie_path`` in place. Returns the final path.

    Raises EmbedError if ffmpeg is missing, there are no tracks, or the mux
    fails. The original file is only replaced after a successful mux.
    """
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        raise EmbedError(
            "ffmpeg was not found on PATH. Install ffmpeg to embed subtitles, "
            "or use sidecar mode instead."
        )
    if not tracks:
        raise EmbedError("No subtitle tracks to embed.")

    directory = os.path.dirname(movie_path)
    _, movie_ext = os.path.splitext(movie_path)
    codec = _subtitle_codec(movie_ext)

    fd, temp_out = tempfile.mkstemp(suffix=movie_ext, dir=directory, prefix=".subgenie_")
    os.close(fd)

    cmd = [ffmpeg, "-y", "-i", movie_path]
    for track in tracks:
        cmd += ["-i", track.path]

    # Map the original streams, then each subtitle input in order.
    cmd += ["-map", "0"]
    for index in range(len(tracks)):
        cmd += ["-map", str(index + 1)]

    # Copy everything; (re)encode only subtitles to the container's codec.
    cmd += ["-c", "copy", "-c:s", codec]

    # Per-subtitle metadata and disposition.
    for sub_index, track in enumerate(tracks):
        cmd += [f"-metadata:s:s:{sub_index}", f"language={track.language.alpha3}"]
        title = track.language.name
        if track.forced:
            title += " (Forced)"
        elif track.hearing_impaired:
            title += " (SDH)"
        cmd += [f"-metadata:s:s:{sub_index}", f"title={title}"]
        if track.forced:
            cmd += [f"-disposition:s:{sub_index}", "forced"]

    cmd.append(temp_out)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError as exc:
        _safe_remove(temp_out)
        raise EmbedError(f"Failed to launch ffmpeg: {exc}") from exc

    if result.returncode != 0:
        _safe_remove(temp_out)
        tail = "\n".join(result.stderr.strip().splitlines()[-8:])
        raise EmbedError(f"ffmpeg failed (exit {result.returncode}):\n{tail}")

    if keep_original:
        backup = movie_path + ".subgenie.bak"
        try:
            os.replace(movie_path, backup)
        except OSError as exc:
            _safe_remove(temp_out)
            raise EmbedError(f"Could not back up original: {exc}") from exc

    try:
        os.replace(temp_out, movie_path)
    except OSError as exc:
        _safe_remove(temp_out)
        raise EmbedError(f"Could not replace original movie file: {exc}") from exc

    return movie_path


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
