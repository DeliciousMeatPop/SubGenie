"""Common types and interface every subtitle provider implements."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..languages import Language
from ..mediainfo import MovieInfo


class ProviderError(Exception):
    """Recoverable provider failure (network, auth, quota).

    Providers raise this instead of leaking arbitrary exceptions so ``core`` can
    log-and-continue to the next provider rather than crashing the whole run.
    """


@dataclass
class SubtitleQuery:
    """Everything a provider needs to search for one movie."""
    info: MovieInfo
    languages: list[Language]
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    prefer_3d: bool = False


@dataclass
class SubtitleCandidate:
    """A single subtitle result, ranked and downloadable.

    ``provider`` keeps a back-reference so ``core`` can call ``download`` on the
    right object without threading provider identity through separately.
    """
    provider: "Provider"
    language: Language
    release: str = ""
    subtitle_ext: str = ".srt"
    forced: bool = False
    hearing_impaired: bool = False
    hash_match: bool = False        # matched by file hash (perfectly synced)
    downloads: int = 0
    rating: float = 0.0
    fps: Optional[float] = None
    # Opaque handle the provider uses to actually fetch the bytes.
    download_ref: dict = field(default_factory=dict)

    def score(self) -> tuple:
        """Sort key (higher is better). Hash match dominates everything."""
        return (
            1 if self.hash_match else 0,
            self.rating,
            self.downloads,
        )


class Provider:
    """Base class. Subclasses implement ``search`` and ``download``."""

    name: str = "provider"

    def is_available(self) -> bool:
        """Whether this provider is usable (e.g. has needed credentials)."""
        return True

    def search(self, query: SubtitleQuery) -> list[SubtitleCandidate]:
        """Return candidates for the query. Raise ProviderError on failure."""
        raise NotImplementedError

    def download(self, candidate: SubtitleCandidate) -> bytes:
        """Fetch the subtitle bytes for a candidate. Raise ProviderError."""
        raise NotImplementedError
