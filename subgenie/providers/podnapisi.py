"""Podnapisi.net provider - a keyless public fallback.

Podnapisi needs no API key, which makes it a useful safety net when the user
hasn't configured OpenSubtitles or when OpenSubtitles has no match. It has no
file-hash search, so results are title/year matches only (never frame-accurate)
and are ranked below any OpenSubtitles hash match by ``core``.

The site's endpoints are unofficial and occasionally change shape, so every
call is defensively wrapped: any failure degrades to "no results" rather than
breaking the run.
"""

from __future__ import annotations

import io
import zipfile
from typing import Optional

from .. import __user_agent__
from ..languages import Language
from .base import Provider, ProviderError, SubtitleCandidate, SubtitleQuery

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

_SEARCH_URL = "https://www.podnapisi.net/subtitles/search/advanced"
_BASE = "https://www.podnapisi.net"
_TIMEOUT = 30
_SUBTITLE_MEMBERS = (".srt", ".ass", ".ssa", ".sub", ".vtt")


class PodnapisiProvider(Provider):
    name = "podnapisi"

    def __init__(self) -> None:
        self._session = requests.Session() if requests else None

    def is_available(self) -> bool:
        return bool(requests)

    def search(self, query: SubtitleQuery) -> list[SubtitleCandidate]:
        if not self.is_available():
            return []
        candidates: list[SubtitleCandidate] = []
        # Podnapisi searches one language at a time.
        for language in query.languages:
            candidates.extend(self._search_one(query, language))
        return candidates

    def _search_one(
        self, query: SubtitleQuery, language: Language
    ) -> list[SubtitleCandidate]:
        params = {
            "keywords": query.info.title,
            "language": language.alpha2 or language.alpha3,
            "movie_type": "movie",
        }
        if query.info.year:
            params["year"] = str(query.info.year)
        headers = {"User-Agent": __user_agent__, "Accept": "application/json"}
        try:
            response = self._session.get(
                _SEARCH_URL, params=params, headers=headers, timeout=_TIMEOUT
            )
        except requests.RequestException:
            return []
        if not response.ok:
            return []
        try:
            payload = response.json()
        except ValueError:
            return []

        results = payload.get("data") or []
        out: list[SubtitleCandidate] = []
        for item in results:
            download = item.get("download") or item.get("url")
            if not download:
                continue
            if download.startswith("/"):
                download = _BASE + download
            flags = " ".join(item.get("flags", [])) if isinstance(item.get("flags"), list) else ""
            out.append(
                SubtitleCandidate(
                    provider=self,
                    language=language,
                    release=str(item.get("title") or item.get("movie") or ""),
                    subtitle_ext=".srt",
                    forced="forced" in flags.lower(),
                    hearing_impaired="hearing" in flags.lower() or "cc" in flags.lower(),
                    hash_match=False,
                    downloads=int(item.get("downloads") or 0),
                    rating=float(item.get("rating") or 0.0),
                    download_ref={"url": download},
                )
            )
        return out

    def download(self, candidate: SubtitleCandidate) -> bytes:
        url = candidate.download_ref.get("url")
        if not url:
            raise ProviderError("Podnapisi candidate has no download URL.")
        headers = {"User-Agent": __user_agent__}
        try:
            response = self._session.get(url, headers=headers, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderError(f"Podnapisi download failed: {exc}") from exc
        if not response.ok:
            raise ProviderError(f"Podnapisi download HTTP {response.status_code}.")

        content = response.content
        # Podnapisi serves a zip; pull the first subtitle member out of it.
        extracted = _extract_subtitle(content)
        if extracted is None:
            raise ProviderError("Podnapisi archive contained no subtitle file.")
        return extracted


def _extract_subtitle(content: bytes) -> Optional[bytes]:
    if not content[:2] == b"PK":  # not a zip; assume it's already a subtitle
        return content
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for name in archive.namelist():
                if name.lower().endswith(_SUBTITLE_MEMBERS):
                    return archive.read(name)
    except zipfile.BadZipFile:
        return None
    return None
