"""OpenSubtitles.com REST API (v1) provider - the primary source.

Docs: https://opensubtitles.stoplight.io/docs/opensubtitles-api

Auth model:
  * An API key (free, from a registered account) is *required* and sent as the
    ``Api-Key`` header on every request.
  * A username/password login is *optional*; it returns a token that raises the
    daily download quota. We log in lazily, only when we first need to download.

Searching is done by file hash first (frame-accurate) and by title/year as a
fallback, all in one request. Downloading is a two-step dance: POST /download
with a ``file_id`` returns a temporary link, which we then GET.
"""

from __future__ import annotations

from typing import Optional

from .. import __user_agent__
from ..languages import Language, find as find_language
from .base import Provider, ProviderError, SubtitleCandidate, SubtitleQuery

try:
    import requests
except ImportError:  # pragma: no cover - requests is a declared dependency
    requests = None  # type: ignore

_API_BASE = "https://api.opensubtitles.com/api/v1"
_TIMEOUT = 30


class OpenSubtitlesProvider(Provider):
    name = "opensubtitles"

    def __init__(self, api_key: str, username: str = "", password: str = ""):
        self.api_key = (api_key or "").strip()
        self.username = username or ""
        self.password = password or ""
        self._token: Optional[str] = None
        self._session = requests.Session() if requests else None

    # -- availability -------------------------------------------------------

    def is_available(self) -> bool:
        return bool(requests and self.api_key)

    def _headers(self, with_token: bool = False) -> dict:
        headers = {
            "Api-Key": self.api_key,
            "User-Agent": __user_agent__,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if with_token and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    # -- search -------------------------------------------------------------

    def search(self, query: SubtitleQuery) -> list[SubtitleCandidate]:
        if not self.is_available():
            raise ProviderError("OpenSubtitles is not configured (missing API key).")

        os_codes = ",".join(sorted({l.os_code for l in query.languages}))
        params: dict[str, str] = {"languages": os_codes}
        if query.file_hash:
            params["moviehash"] = query.file_hash
        # Always include a text query too, so a hash miss still returns results.
        if query.info.title:
            params["query"] = query.info.title
        if query.info.year:
            params["year"] = str(query.info.year)

        try:
            response = self._session.get(
                f"{_API_BASE}/subtitles",
                params=params,
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"OpenSubtitles search failed: {exc}") from exc

        if response.status_code == 401:
            raise ProviderError("OpenSubtitles rejected the API key (401).")
        if response.status_code == 429:
            raise ProviderError("OpenSubtitles rate limit hit (429). Try again later.")
        if not response.ok:
            raise ProviderError(f"OpenSubtitles search HTTP {response.status_code}.")

        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError("OpenSubtitles returned invalid JSON.") from exc

        return self._parse_results(payload.get("data", []), query.languages)

    def _parse_results(
        self, data: list, requested: list[Language]
    ) -> list[SubtitleCandidate]:
        by_os_code = {l.os_code: l for l in requested}
        candidates: list[SubtitleCandidate] = []
        for item in data:
            attrs = item.get("attributes", {}) or {}
            files = attrs.get("files") or []
            if not files:
                continue
            file_id = files[0].get("file_id")
            if file_id is None:
                continue

            language = by_os_code.get(attrs.get("language")) or find_language(
                attrs.get("language", "")
            )
            if language is None:
                continue

            candidates.append(
                SubtitleCandidate(
                    provider=self,
                    language=language,
                    release=(attrs.get("release") or "").strip(),
                    subtitle_ext=".srt",
                    forced=bool(attrs.get("foreign_parts_only")),
                    hearing_impaired=bool(attrs.get("hearing_impaired")),
                    hash_match=bool(attrs.get("moviehash_match")),
                    downloads=int(attrs.get("download_count") or 0),
                    rating=float(attrs.get("ratings") or 0.0),
                    fps=_safe_float(attrs.get("fps")),
                    download_ref={"file_id": file_id},
                )
            )
        return candidates

    # -- download -----------------------------------------------------------

    def _login(self) -> None:
        if self._token or not (self.username and self.password):
            return
        try:
            response = self._session.post(
                f"{_API_BASE}/login",
                json={"username": self.username, "password": self.password},
                headers=self._headers(),
                timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"OpenSubtitles login failed: {exc}") from exc
        if response.ok:
            self._token = response.json().get("token")

    def download(self, candidate: SubtitleCandidate) -> bytes:
        if not self.is_available():
            raise ProviderError("OpenSubtitles is not configured.")
        file_id = candidate.download_ref.get("file_id")
        if file_id is None:
            raise ProviderError("Candidate has no OpenSubtitles file_id.")

        self._login()  # best-effort; raises the quota if it works.

        try:
            response = self._session.post(
                f"{_API_BASE}/download",
                json={"file_id": file_id},
                headers=self._headers(with_token=True),
                timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise ProviderError(f"OpenSubtitles download request failed: {exc}") from exc

        if response.status_code == 406 or response.status_code == 429:
            raise ProviderError(
                "OpenSubtitles download quota exhausted for now. "
                "Add a username/password in config for a higher quota."
            )
        if not response.ok:
            raise ProviderError(f"OpenSubtitles download HTTP {response.status_code}.")

        link = response.json().get("link")
        if not link:
            raise ProviderError("OpenSubtitles did not return a download link.")

        try:
            file_response = self._session.get(link, timeout=_TIMEOUT)
        except requests.RequestException as exc:
            raise ProviderError(f"Fetching subtitle file failed: {exc}") from exc
        if not file_response.ok:
            raise ProviderError(f"Subtitle download HTTP {file_response.status_code}.")
        return file_response.content


def _safe_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
