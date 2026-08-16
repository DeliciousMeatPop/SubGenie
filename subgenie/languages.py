"""Language table and lookup helpers.

Each entry carries everything the rest of the app needs:
  * ``name``     - human readable English name
  * ``alpha2``   - ISO 639-1 two-letter code (used for sidecar filenames)
  * ``alpha3``   - ISO 639-2 three-letter code (used for embedded track metadata)
  * ``os_code``  - the code OpenSubtitles expects in its ``languages`` param

Sidecar naming uses ``alpha2`` when available (Plex/Jellyfin both understand
two-letter codes and it keeps filenames short); embedding uses ``alpha3``
because Matroska/MP4 track metadata is three-letter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class Language:
    name: str
    alpha2: str
    alpha3: str
    os_code: str

    @property
    def sidecar_code(self) -> str:
        """Code used in sidecar filenames (prefers the short ISO 639-1 code)."""
        return self.alpha2 or self.alpha3


# A curated but broad set of the languages people actually download subtitles
# for. Not exhaustive of all 7000 human languages, but covers the long tail of
# real subtitle catalogues. os_code follows OpenSubtitles' own list, which uses
# region variants for a handful of languages (pt-BR, zh-CN, ...).
_LANGUAGES: list[Language] = [
    Language("Arabic", "ar", "ara", "ar"),
    Language("Bengali", "bn", "ben", "bn"),
    Language("Bulgarian", "bg", "bul", "bg"),
    Language("Catalan", "ca", "cat", "ca"),
    Language("Chinese (Simplified)", "zh", "chi", "zh-CN"),
    Language("Chinese (Traditional)", "zt", "zht", "zh-TW"),
    Language("Croatian", "hr", "hrv", "hr"),
    Language("Czech", "cs", "cze", "cs"),
    Language("Danish", "da", "dan", "da"),
    Language("Dutch", "nl", "dut", "nl"),
    Language("English", "en", "eng", "en"),
    Language("Estonian", "et", "est", "et"),
    Language("Finnish", "fi", "fin", "fi"),
    Language("French", "fr", "fre", "fr"),
    Language("German", "de", "ger", "de"),
    Language("Greek", "el", "ell", "el"),
    Language("Hebrew", "he", "heb", "he"),
    Language("Hindi", "hi", "hin", "hi"),
    Language("Hungarian", "hu", "hun", "hu"),
    Language("Icelandic", "is", "ice", "is"),
    Language("Indonesian", "id", "ind", "id"),
    Language("Italian", "it", "ita", "it"),
    Language("Japanese", "ja", "jpn", "ja"),
    Language("Korean", "ko", "kor", "ko"),
    Language("Latvian", "lv", "lav", "lv"),
    Language("Lithuanian", "lt", "lit", "lt"),
    Language("Malay", "ms", "may", "ms"),
    Language("Norwegian", "no", "nor", "no"),
    Language("Persian", "fa", "per", "fa"),
    Language("Polish", "pl", "pol", "pl"),
    Language("Portuguese", "pt", "por", "pt-PT"),
    Language("Portuguese (Brazil)", "pb", "pob", "pt-BR"),
    Language("Romanian", "ro", "rum", "ro"),
    Language("Russian", "ru", "rus", "ru"),
    Language("Serbian", "sr", "srp", "sr"),
    Language("Slovak", "sk", "slo", "sk"),
    Language("Slovenian", "sl", "slv", "sl"),
    Language("Spanish", "es", "spa", "es"),
    Language("Spanish (Latin America)", "ea", "spl", "es-419"),
    Language("Swedish", "sv", "swe", "sv"),
    Language("Tagalog", "tl", "tgl", "tl"),
    Language("Thai", "th", "tha", "th"),
    Language("Turkish", "tr", "tur", "tr"),
    Language("Ukrainian", "uk", "ukr", "uk"),
    Language("Vietnamese", "vi", "vie", "vi"),
]

# Build lookup indexes once.
_BY_ANY: dict[str, Language] = {}
for _lang in _LANGUAGES:
    for _key in (_lang.name.lower(), _lang.alpha2, _lang.alpha3, _lang.os_code.lower()):
        if _key:
            _BY_ANY.setdefault(_key, _lang)


# A handy "common" preset — the languages people usually actually want, instead
# of dumping all 40-odd. Keeps both Spanish and Portuguese variants distinct.
_COMMON_CODES = ["en", "es", "ea", "fr", "de", "it", "pt", "pb", "nl"]


def all_languages() -> list[Language]:
    """Return the full language table (sorted by name)."""
    return sorted(_LANGUAGES, key=lambda l: l.name)


def common_languages() -> list[Language]:
    """Return the curated 'common' language set, in preset order."""
    out: list[Language] = []
    for code in _COMMON_CODES:
        lang = find(code)
        if lang is not None:
            out.append(lang)
    return out


def find(token: str) -> Optional[Language]:
    """Resolve a user-supplied token (name/alpha2/alpha3/os_code) to a Language.

    Case-insensitive. Returns ``None`` if nothing matches so callers can warn
    instead of silently dropping a requested language.
    """
    if not token:
        return None
    return _BY_ANY.get(token.strip().lower())


def resolve_many(tokens: Iterable[str]) -> tuple[list[Language], list[str]]:
    """Resolve many tokens, returning (found languages, unknown tokens).

    Order is preserved and duplicates removed. ``all`` expands to every
    language; ``common`` expands to the curated common set.
    """
    found: list[Language] = []
    unknown: list[str] = []
    seen: set[str] = set()

    def _extend(langs: list[Language]) -> None:
        for lang in langs:
            if lang.alpha3 not in seen:
                seen.add(lang.alpha3)
                found.append(lang)

    for raw in tokens:
        token = raw.strip()
        if not token:
            continue
        if token.lower() == "all":
            _extend(all_languages())
            continue
        if token.lower() == "common":
            _extend(common_languages())
            continue
        lang = find(token)
        if lang is None:
            unknown.append(token)
        elif lang.alpha3 not in seen:
            seen.add(lang.alpha3)
            found.append(lang)
    return found, unknown
