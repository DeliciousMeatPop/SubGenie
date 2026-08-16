"""Decode subtitle bytes to text, using the subtitle's known language.

Downloaded subtitles are frequently **not** UTF-8. Non-Latin languages arrive in
legacy code pages — Windows-1256 (Arabic), 1251 (Cyrillic), 1253 (Greek),
GBK/Big5 (Chinese), Shift-JIS (Japanese)… Decoding those as UTF-8 mangles the
text, so once rewritten (e.g. into a 3D ``.ass``) they show garbage or nothing —
while plain-ASCII English survives, which is exactly the "English works, the
rest don't" symptom.

Blind charset detection is unreliable on subtitle-sized samples (it happily
guesses a wrong single-byte or CJK page), so we lean on the strongest signal we
have: SubtitleGenie already knows each subtitle's language. We try UTF-8 first
(most modern subs), then the legacy encodings that language is actually written
in, then charset-normalizer, then a Latin-1 last resort that never raises.
"""

from __future__ import annotations

from typing import Optional

_CYRILLIC = ("cp1251", "koi8-r", "iso-8859-5")
_CENTRAL_EU = ("cp1250", "iso-8859-2")

# alpha2 -> ordered legacy encodings to try after UTF-8.
_LANG_ENCODINGS: dict[str, tuple[str, ...]] = {
    "ar": ("cp1256", "iso-8859-6"),
    "fa": ("cp1256",),
    "he": ("cp1255", "iso-8859-8"),
    "el": ("cp1253", "iso-8859-7"),
    "tr": ("cp1254", "iso-8859-9"),
    "th": ("cp874", "tis-620"),
    "vi": ("cp1258",),
    "zh": ("gb18030", "gbk"),
    "zt": ("big5", "gb18030"),
    "ja": ("cp932", "euc-jp", "shift_jis"),
    "ko": ("cp949", "euc-kr"),
    # Cyrillic-script languages.
    "ru": _CYRILLIC, "bg": _CYRILLIC, "sr": _CYRILLIC, "uk": _CYRILLIC, "mk": _CYRILLIC,
    # Central-European Latin.
    "pl": _CENTRAL_EU, "cs": _CENTRAL_EU, "sk": _CENTRAL_EU, "hu": _CENTRAL_EU,
    "ro": _CENTRAL_EU, "hr": _CENTRAL_EU, "sl": _CENTRAL_EU,
}

_DEFAULT_LEGACY = ("cp1252", "iso-8859-15", "iso-8859-1")


def _try(data: bytes, encodings) -> Optional[str]:
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return None


def decode_subtitle(data: bytes, lang: Optional[str] = None) -> str:
    """Decode subtitle bytes to ``str``, guided by the subtitle's language."""
    if not data:
        return ""

    # 1) UTF-8 (with/without BOM) - the modern common case.
    text = _try(data, ("utf-8-sig", "utf-8"))
    if text is not None:
        return text

    # 2) The legacy encodings this language is actually written in.
    if lang:
        text = _try(data, _LANG_ENCODINGS.get(lang.lower(), ()))
        if text is not None:
            return text

    # 3) Statistical detection (charset-normalizer ships with requests).
    try:
        from charset_normalizer import from_bytes

        best = from_bytes(data).best()
        if best is not None:
            return str(best)
    except Exception:  # noqa: BLE001 - detection must never break a run
        pass

    # 4) Last resorts; latin-1 maps every byte and never raises.
    text = _try(data, _DEFAULT_LEGACY + ("latin-1",))
    return text if text is not None else data.decode("utf-8", errors="replace")
