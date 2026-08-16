"""Parse what we can from a movie file *without* external services.

We deliberately keep this dependency-free (no guessit) so SubtitleGenie stays a
light install. The parser is heuristic but tuned for how scene/release and
personal-library filenames actually look, and it specifically understands the
zoo of 3D tags (SBS, HSBS, Half-OU, etc.).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

# Extensions we treat as movie/video containers.
VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".flv",
    ".webm", ".mpg", ".mpeg", ".ts", ".m2ts", ".vob", ".ogm", ".divx",
}

# Extensions we treat as subtitle files (for detecting what already exists).
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".sub", ".vtt", ".sup"}

# 3D format tags. Keys are canonical, values are the regexes that spot them.
_THREE_D_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("HSBS", re.compile(r"\b(?:h[-. ]?sbs|half[-. ]?sbs)\b", re.I)),
    ("HOU", re.compile(r"\b(?:h[-. ]?ou|half[-. ]?ou|htab|h[-. ]?tab)\b", re.I)),
    ("SBS", re.compile(r"\b(?:full[-. ]?sbs|f[-. ]?sbs|sbs)\b", re.I)),
    ("OU", re.compile(r"\b(?:full[-. ]?ou|f[-. ]?ou|ou|tab)\b", re.I)),
    ("3D", re.compile(r"\b(?:3d|3-d)\b", re.I)),
]

# Junk tokens that mark the end of the real title in a release name.
_STOP_TOKENS = re.compile(
    r"\b("
    r"480p|576p|720p|1080p|1080i|2160p|4k|uhd|hdr|dovi|dv|"
    r"bluray|blu-ray|brrip|bdrip|bdremux|remux|web-?dl|webrip|web|"
    r"hdrip|dvdrip|dvdscr|hdtv|pdtv|cam|ts|tc|"
    r"x264|x265|h264|h265|hevc|avc|xvid|divx|"
    r"aac|ac3|dts|dts-hd|truehd|atmos|ddp?5\.1|dd5\.1|flac|mp3|"
    r"3d|sbs|hsbs|ou|hou|tab|htab|"
    r"proper|repack|extended|unrated|remastered|imax|"
    r"multi|dual|internal"
    r")\b",
    re.I,
)

_YEAR = re.compile(r"(?:^|[^\d])((?:19|20)\d{2})(?:[^\d]|$)")


@dataclass
class MovieInfo:
    path: str
    directory: str
    filename: str          # basename without extension
    extension: str         # lowercased, includes leading dot
    title: str
    year: Optional[int]
    is_3d: bool
    three_d_format: Optional[str]   # canonical tag (SBS/HSBS/OU/HOU/3D) or None
    raw_tokens: list[str] = field(default_factory=list)

    @property
    def sidecar_base(self) -> str:
        """Path stem used to build sidecar subtitle filenames (no extension)."""
        return os.path.join(self.directory, self.filename)


def is_video_file(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS


def detect_3d(name: str) -> tuple[bool, Optional[str]]:
    """Return (is_3d, canonical_format) from a release/file name."""
    for canonical, pattern in _THREE_D_PATTERNS:
        if pattern.search(name):
            return True, canonical
    return False, None


def _clean_title(raw: str) -> str:
    # Release names use dots/underscores as spaces; personal names use spaces.
    text = raw.replace("_", " ")
    # Only convert dots to spaces if there are no spaces already (scene style).
    if "." in text and " " not in text.strip():
        text = text.replace(".", " ")
    text = re.sub(r"\s+", " ", text).strip(" -[](){}")
    return text


def parse(path: str) -> MovieInfo:
    """Parse a movie path into a MovieInfo (best-effort, never raises)."""
    directory = os.path.dirname(os.path.abspath(path))
    base = os.path.basename(path)
    stem, ext = os.path.splitext(base)
    ext = ext.lower()

    is_3d, three_d_format = detect_3d(stem)

    # Find the year and treat everything before it as the title. Movies almost
    # always carry a year; if there's no year we cut at the first junk token.
    year: Optional[int] = None
    title_part = stem
    year_match = _YEAR.search(stem)
    if year_match:
        year = int(year_match.group(1))
        title_part = stem[: year_match.start(1)]
    else:
        stop = _STOP_TOKENS.search(stem)
        if stop:
            title_part = stem[: stop.start()]

    title = _clean_title(title_part) or _clean_title(stem)

    return MovieInfo(
        path=os.path.abspath(path),
        directory=directory,
        filename=stem,
        extension=ext,
        title=title,
        year=year,
        is_3d=is_3d,
        three_d_format=three_d_format,
        raw_tokens=re.split(r"[.\s_]+", stem),
    )


def existing_sidecar_languages(info: MovieInfo) -> set[str]:
    """Return the set of language codes that already have a sidecar next to the
    movie, so we can skip re-downloading them unless the user forces overwrite.

    Matches ``<moviename>.<lang>[.flags].<ext>`` and returns the ``<lang>`` token
    lowercased. It's a best-effort scan of sibling files.
    """
    langs: set[str] = set()
    prefix = info.filename + "."
    try:
        siblings = os.listdir(info.directory)
    except OSError:
        return langs
    for name in siblings:
        stem, ext = os.path.splitext(name)
        if ext.lower() not in SUBTITLE_EXTENSIONS:
            continue
        if not name.startswith(prefix):
            continue
        # tokens after the movie name; first token is the language code.
        remainder = name[len(prefix):]
        remainder = os.path.splitext(remainder)[0]
        parts = remainder.split(".")
        if parts and parts[0]:
            langs.add(parts[0].lower())
    return langs


def sidecar_subtitle_files(info: MovieInfo) -> list[str]:
    """Full paths of subtitle files sitting next to the movie (its sidecars).

    Matches ``<moviename>.<...>.<ext>`` for known subtitle extensions. Used by
    the sync-in-place flow to re-time subtitles you already have.
    """
    found: list[str] = []
    prefix = info.filename + "."
    try:
        siblings = sorted(os.listdir(info.directory))
    except OSError:
        return found
    for name in siblings:
        ext = os.path.splitext(name)[1].lower()
        if ext in SUBTITLE_EXTENSIONS and name.startswith(prefix):
            found.append(os.path.join(info.directory, name))
    return found
