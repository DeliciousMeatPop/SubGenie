"""Build sidecar subtitle filenames that media servers understand.

Convention (Plex & Jellyfin both read this):

    <movie basename>.<lang>[.forced][.sdh][.N].<ext>

  * ``<movie basename>`` is the movie's filename without extension, so the
    subtitle sits right next to it and inherits any 3D tag automatically.
  * ``<lang>`` is the ISO 639-1 code where possible.
  * ``.forced`` marks forced/foreign-parts-only tracks.
  * ``.sdh`` marks hearing-impaired (SDH) tracks.
  * ``.N`` is a disambiguating counter only when a name would otherwise collide.
"""

from __future__ import annotations

import os

from .languages import Language
from .mediainfo import MovieInfo


def sidecar_filename(
    info: MovieInfo,
    language: Language,
    *,
    forced: bool = False,
    hearing_impaired: bool = False,
    subtitle_ext: str = ".srt",
) -> str:
    """Return the sidecar filename (no directory) for one subtitle."""
    if not subtitle_ext.startswith("."):
        subtitle_ext = "." + subtitle_ext
    parts = [info.filename, language.sidecar_code]
    if forced:
        parts.append("forced")
    if hearing_impaired:
        parts.append("sdh")
    return ".".join(parts) + subtitle_ext.lower()


def sidecar_path(
    info: MovieInfo,
    language: Language,
    *,
    forced: bool = False,
    hearing_impaired: bool = False,
    subtitle_ext: str = ".srt",
    overwrite: bool = False,
) -> str:
    """Return a full sidecar path, adding a ``.N`` counter to avoid clobbering.

    When ``overwrite`` is True we return the canonical name even if it exists
    (the caller intends to replace it). Otherwise we find the first free
    ``.N`` variant.
    """
    name = sidecar_filename(
        info,
        language,
        forced=forced,
        hearing_impaired=hearing_impaired,
        subtitle_ext=subtitle_ext,
    )
    path = os.path.join(info.directory, name)
    if overwrite or not os.path.exists(path):
        return path

    stem, ext = os.path.splitext(name)
    counter = 2
    while True:
        candidate = os.path.join(info.directory, f"{stem}.{counter}{ext}")
        if not os.path.exists(candidate):
            return candidate
        counter += 1
