"""Mux subtitle files into a movie container using ffmpeg.

We copy **every existing stream untouched** and append each subtitle file as a
new soft-subtitle track. Nothing that's already in the movie is re-encoded -
crucially, existing subtitle tracks (which on BluRay rips are often *bitmap*
PGS subs) are copied as-is. An earlier version forced ``-c:s <codec>`` across
all subtitle streams, which made ffmpeg try to transcode those bitmap subs to
text and fail with "Subtitle encoding currently only possible from text to text
or bitmap to bitmap".

So the codec and language/forced metadata are applied **only to the subtitle
streams we add**, addressed at the right offset (after however many subtitle
streams the movie already had). For MKV our .ass/.srt inputs are simply copied
in; only MP4 output needs its added text subs converted to ``mov_text``.

The result is written to a temp file in the same directory and then atomically
swapped over the original (optionally keeping a backup), so an interrupted mux
never corrupts the source file.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

from . import ffmpeg as ffmpeg_tools
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
    # Looks on PATH first, then in SubtitleGenie's own install dir.
    return ffmpeg_tools.ffmpeg_path()


def ffprobe_path() -> Optional[str]:
    return ffmpeg_tools.ffprobe_path()


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


def subtitle_stream_count(movie_path: str) -> int:
    """How many subtitle streams the movie already has (0 if ffprobe absent).

    This is the offset at which our newly-added subtitle streams land in the
    output, so language/forced metadata gets applied to the right tracks.
    """
    probe = ffprobe_path()
    if not probe:
        return 0
    cmd = [
        probe, "-v", "error",
        "-select_streams", "s",
        "-show_entries", "stream=index",
        "-of", "csv=p=0",
        movie_path,
    ]
    try:
        output = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    return len([line for line in output.splitlines() if line.strip()])


def subtitle_track_languages(movie_path: str) -> list[str]:
    """Language tag (lowercased, '' if none) of each existing subtitle stream, in order.

    Used to find which existing track matches the user's preferred language so it
    can be marked the default (auto-selected) track. Empty list if ffprobe absent.
    """
    probe = ffprobe_path()
    if not probe:
        return []
    cmd = [
        probe, "-v", "error",
        "-select_streams", "s",
        "-show_entries", "stream=index:stream_tags=language",
        "-of", "csv=p=0",
        movie_path,
    ]
    try:
        output = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60, check=False
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    langs: list[str] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        # "index,lang" or "index," when the stream has no language tag.
        parts = line.split(",", 1)
        langs.append(parts[1].strip().lower() if len(parts) > 1 else "")
    return langs


def _added_subtitle_codec(output_ext: str) -> str:
    """Codec for the subtitle streams we add (existing ones are always copied).

    MKV carries .ass/.srt natively, so we copy them straight in (this also keeps
    3D per-eye ASS positioning intact). MP4 can only hold ``mov_text``, so text
    subs are converted for it.
    """
    if output_ext.lower() in (".mp4", ".m4v", ".mov"):
        return "mov_text"
    return "copy"


def _preferred_subtitle_index(
    movie_path: str,
    tracks: list[SubtitleTrack],
    offset: int,
    default_alpha3: Optional[str],
) -> Optional[int]:
    """Subtitle-stream index that should be the default, or None.

    Prefers a track we're adding in the wanted language; otherwise an existing
    track already in that language (e.g. the movie's own English). None when no
    preference is given or nothing matches, leaving dispositions as-is.
    """
    if not default_alpha3:
        return None
    for i, track in enumerate(tracks):
        if track.language.alpha3 == default_alpha3:
            return offset + i
    for i, lang in enumerate(subtitle_track_languages(movie_path)):
        if lang == default_alpha3:
            return i
    return None


def embed_subtitles(
    movie_path: str,
    tracks: list[SubtitleTrack],
    *,
    keep_original: bool = False,
    tag: str = "SG",
    default_alpha3: Optional[str] = None,
    progress=None,
) -> str:
    """Mux ``tracks`` into ``movie_path`` in place. Returns the final path.

    Raises EmbedError if ffmpeg is missing, there are no tracks, or the mux
    fails. The original file is only replaced after a successful mux. ``progress``
    (optional) is called with a 0..1 fraction as the mux proceeds.
    """
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        raise EmbedError(
            "ffmpeg was not found. Install it to embed subtitles, or use sidecar "
            "mode instead.\n\n" + ffmpeg_tools.guidance()
        )
    if not tracks:
        raise EmbedError("No subtitle tracks to embed.")

    directory = os.path.dirname(movie_path)
    _, movie_ext = os.path.splitext(movie_path)
    added_codec = _added_subtitle_codec(movie_ext)

    # Where our added subtitle streams start, in the output's subtitle-stream
    # numbering: right after the movie's existing subtitle streams.
    offset = subtitle_stream_count(movie_path)

    fd, temp_out = tempfile.mkstemp(suffix=movie_ext, dir=directory, prefix=".subgenie_")
    os.close(fd)

    cmd = [ffmpeg, "-y", "-i", movie_path]
    for track in tracks:
        cmd += ["-i", track.path]

    # Map the original streams, then each subtitle input in order.
    cmd += ["-map", "0"]
    for index in range(len(tracks)):
        cmd += ["-map", str(index + 1)]

    # Copy EVERY stream by default - existing subs (even bitmap PGS) are never
    # transcoded. We only override the codec/metadata for the subtitle streams
    # we add, addressed at offset+i so they don't clobber the movie's own subs.
    cmd += ["-c", "copy"]

    # Decide which subtitle stream should be the default (auto-selected) track:
    # the user's preferred language, whether it's one we're adding or one the
    # movie already has. Falls back to leaving dispositions untouched.
    pref_index = _preferred_subtitle_index(movie_path, tracks, offset, default_alpha3)

    for i, track in enumerate(tracks):
        s = offset + i
        if added_codec != "copy":
            cmd += [f"-c:s:{s}", added_codec]
        cmd += [f"-metadata:s:s:{s}", f"language={track.language.alpha3}"]
        title = f"{track.language.name} [{tag}]" if tag else track.language.name
        if track.forced:
            title += " (Forced)"
        elif track.hearing_impaired:
            title += " (SDH)"
        cmd += [f"-metadata:s:s:{s}", f"title={title}"]

    if pref_index is not None:
        # Clear default on the movie's own subtitle streams so ours can win.
        for i in range(offset):
            cmd += [f"-disposition:s:{i}", "+default" if i == pref_index else "-default"]

    # Absolute disposition for the streams we add (forced / default / none).
    for i, track in enumerate(tracks):
        s = offset + i
        flags = []
        if track.forced:
            flags.append("forced")
        if s == pref_index:
            flags.append("default")
        cmd += [f"-disposition:s:{s}", "+".join(flags) if flags else "0"]

    cmd.append(temp_out)

    try:
        if progress is not None:
            returncode, stderr_tail = _run_with_progress(cmd, movie_path, progress)
        else:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            returncode = result.returncode
            stderr_tail = "\n".join(result.stderr.strip().splitlines()[-8:])
    except OSError as exc:
        _safe_remove(temp_out)
        raise EmbedError(f"Failed to launch ffmpeg: {exc}") from exc

    if returncode != 0:
        _safe_remove(temp_out)
        raise EmbedError(f"ffmpeg failed (exit {returncode}):\n{stderr_tail}")

    if keep_original:
        backup = movie_path + ".subgenie.bak"
        try:
            _replace_with_retry(movie_path, backup)
        except OSError as exc:
            _safe_remove(temp_out)
            raise EmbedError(f"Could not back up original: {exc}") from exc

    try:
        _replace_with_retry(temp_out, movie_path)
    except OSError as exc:
        _safe_remove(temp_out)
        raise EmbedError(
            f"Could not replace the movie file: {exc}\n"
            "Something has it open — close the movie in your player, and antivirus "
            "may be scanning the freshly-written file. Try again, or use sidecar mode."
        ) from exc

    return movie_path


def _replace_with_retry(src: str, dst: str, attempts: int = 6) -> None:
    """os.replace with retries — Windows briefly locks just-written large files
    (antivirus / indexer), which makes the swap fail with a sharing violation."""
    import time
    delay = 0.5
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
            delay = min(delay * 2, 4.0)


def _movie_duration(movie_path: str) -> Optional[float]:
    probe = ffprobe_path()
    if not probe:
        return None
    cmd = [probe, "-v", "error", "-show_entries", "format=duration",
           "-of", "default=nw=1:nk=1", movie_path]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


_OUT_TIME = "out_time="


def _run_with_progress(cmd, movie_path, progress):
    """Run ffmpeg with -progress, reporting a 0..1 fraction. Returns (rc, tail)."""
    duration = _movie_duration(movie_path)
    # Insert progress reporting right after the ffmpeg binary. stderr goes to a
    # temp file so its pipe buffer can never fill and deadlock the stdout read.
    full = [cmd[0], "-nostats", "-progress", "pipe:1"] + cmd[1:]
    with tempfile.TemporaryFile(mode="w+") as errfile:
        proc = subprocess.Popen(full, stdout=subprocess.PIPE, stderr=errfile, text=True)
        for line in proc.stdout:
            if duration and line.startswith(_OUT_TIME):
                seconds = _parse_out_time(line[len(_OUT_TIME):].strip())
                if seconds is not None:
                    progress(seconds / duration)
        proc.wait()
        errfile.seek(0)
        tail = errfile.read().strip().splitlines()[-8:]
    if proc.returncode == 0:
        progress(1.0)
    return proc.returncode, "\n".join(tail)


def _parse_out_time(value: str) -> Optional[float]:
    # value like "00:01:23.456789" (or "N/A" early on).
    try:
        h, m, s = value.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except (ValueError, AttributeError):
        return None


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass
