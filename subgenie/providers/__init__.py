"""Subtitle source providers.

``OpenSubtitlesProvider`` is the primary, hash-accurate source; the others are
best-effort public fallbacks used only when OpenSubtitles comes up empty (or has
no API key configured). All providers implement the same small interface from
``base`` so ``core`` can treat them uniformly.
"""

from .base import Provider, SubtitleCandidate, SubtitleQuery, ProviderError
from .opensubtitles import OpenSubtitlesProvider
from .podnapisi import PodnapisiProvider

__all__ = [
    "Provider",
    "SubtitleCandidate",
    "SubtitleQuery",
    "ProviderError",
    "OpenSubtitlesProvider",
    "PodnapisiProvider",
]
