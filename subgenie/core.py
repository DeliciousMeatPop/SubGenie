"""Orchestration: turn a resolved set of options into downloaded/embedded subs.

The interactive "asking" lives in the CLI; by the time we get here every
decision is concrete (which languages, sidecar vs embed, treat as 3D, whether
to overwrite). That split keeps this module pure and testable: given options and
a list of providers, it searches, picks the best candidate per language,
downloads it, and either writes sidecars or muxes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import hashing
from .config import ACTION_EMBED, ACTION_SIDECAR
from .embed import EmbedError, SubtitleTrack, embed_subtitles, embedded_languages
from .languages import Language
from .mediainfo import MovieInfo, existing_sidecar_languages
from .naming import sidecar_path
from .providers.base import Provider, ProviderError, SubtitleCandidate, SubtitleQuery


@dataclass
class RunOptions:
    languages: list[Language]
    action: str = ACTION_SIDECAR          # sidecar | embed
    treat_as_3d: bool = False
    overwrite: bool = False
    keep_original_on_embed: bool = False
    hearing_impaired: str = "include"     # include | prefer | exclude
    forced: str = "include"               # include | prefer | exclude | only


@dataclass
class LanguageOutcome:
    language: Language
    status: str                            # downloaded | embedded | skipped | notfound | error
    detail: str = ""
    path: Optional[str] = None


@dataclass
class MovieResult:
    info: MovieInfo
    outcomes: list[LanguageOutcome] = field(default_factory=list)
    embedded_path: Optional[str] = None
    error: Optional[str] = None


# A callback for progress/log lines. Defaults to a no-op so core stays quiet in
# tests; the CLI passes a real logger.
Logger = Callable[[str], None]


def _noop(_: str) -> None:  # pragma: no cover - trivial
    pass


def _passes_filters(cand: SubtitleCandidate, options: RunOptions) -> bool:
    if options.hearing_impaired == "exclude" and cand.hearing_impaired:
        return False
    if options.forced == "exclude" and cand.forced:
        return False
    if options.forced == "only" and not cand.forced:
        return False
    return True


def _preference_bonus(cand: SubtitleCandidate, options: RunOptions) -> tuple:
    """Extra ranking layer for soft preferences (applied after the base score)."""
    hi_bonus = 1 if (options.hearing_impaired == "prefer" and cand.hearing_impaired) else 0
    forced_bonus = 1 if (options.forced == "prefer" and cand.forced) else 0
    threed_bonus = 1 if (options.treat_as_3d and _looks_3d(cand.release)) else 0
    return (threed_bonus, forced_bonus, hi_bonus)


def _looks_3d(release: str) -> bool:
    lowered = release.lower()
    return any(tag in lowered for tag in ("3d", "sbs", "hsbs", "hou", "half-ou", " ou "))


def best_candidate_per_language(
    candidates: list[SubtitleCandidate], options: RunOptions
) -> dict[str, SubtitleCandidate]:
    """Pick the single best candidate for each language code."""
    best: dict[str, SubtitleCandidate] = {}
    for cand in candidates:
        if not _passes_filters(cand, options):
            continue
        key = cand.language.alpha3
        current = best.get(key)
        cand_rank = (_preference_bonus(cand, options), cand.score())
        if current is None:
            best[key] = cand
            continue
        current_rank = (_preference_bonus(current, options), current.score())
        if cand_rank > current_rank:
            best[key] = cand
    return best


def _gather_existing(info: MovieInfo, options: RunOptions) -> set[str]:
    """Language tokens already present (sidecars + embedded), lowercased.

    Returns both alpha2 and alpha3 forms so either naming scheme is matched.
    """
    existing = set(existing_sidecar_languages(info))
    if options.action == ACTION_EMBED:
        existing |= embedded_languages(info.path)
    return existing


def _already_present(lang: Language, existing: set[str]) -> bool:
    return bool({lang.alpha2, lang.alpha3, lang.sidecar_code} & existing)


def process_movie(
    info: MovieInfo,
    options: RunOptions,
    providers: list[Provider],
    *,
    log: Logger = _noop,
) -> MovieResult:
    """Find and place subtitles for a single movie."""
    result = MovieResult(info=info)

    file_hash = hashing.compute_hash(info.path)
    try:
        file_size = os.path.getsize(info.path)
    except OSError:
        file_size = None

    existing = set() if options.overwrite else _gather_existing(info, options)

    wanted = [l for l in options.languages if not _already_present(l, existing)]
    skipped = [l for l in options.languages if _already_present(l, existing)]
    for lang in skipped:
        result.outcomes.append(
            LanguageOutcome(lang, "skipped", "already present (use overwrite to replace)")
        )

    if not wanted:
        return result

    query = SubtitleQuery(
        info=info,
        languages=wanted,
        file_hash=file_hash,
        file_size=file_size,
        prefer_3d=options.treat_as_3d,
    )

    # Query providers in order; stop early once every wanted language is covered.
    all_candidates: list[SubtitleCandidate] = []
    covered: set[str] = set()
    for provider in providers:
        if not provider.is_available():
            continue
        remaining = [l for l in wanted if l.alpha3 not in covered]
        if not remaining:
            break
        try:
            found = provider.search(SubtitleQuery(
                info=info, languages=remaining, file_hash=file_hash,
                file_size=file_size, prefer_3d=options.treat_as_3d,
            ))
        except ProviderError as exc:
            log(f"  [{provider.name}] {exc}")
            continue
        all_candidates.extend(found)
        covered |= {c.language.alpha3 for c in found}

    best = best_candidate_per_language(all_candidates, options)

    # Download the chosen subtitles.
    downloaded: list[tuple[Language, bytes, SubtitleCandidate]] = []
    for lang in wanted:
        cand = best.get(lang.alpha3)
        if cand is None:
            result.outcomes.append(LanguageOutcome(lang, "notfound", "no subtitle found"))
            continue
        try:
            data = cand.provider.download(cand)
        except ProviderError as exc:
            result.outcomes.append(LanguageOutcome(lang, "error", str(exc)))
            continue
        downloaded.append((lang, data, cand))

    if options.action == ACTION_EMBED:
        _place_embedded(info, options, downloaded, result, log)
    else:
        _place_sidecars(info, options, downloaded, result)

    return result


def _place_sidecars(
    info: MovieInfo,
    options: RunOptions,
    downloaded: list[tuple[Language, bytes, SubtitleCandidate]],
    result: MovieResult,
) -> None:
    for lang, data, cand in downloaded:
        path = sidecar_path(
            info, lang,
            forced=cand.forced,
            hearing_impaired=cand.hearing_impaired,
            subtitle_ext=cand.subtitle_ext,
            overwrite=options.overwrite,
        )
        try:
            with open(path, "wb") as handle:
                handle.write(data)
        except OSError as exc:
            result.outcomes.append(LanguageOutcome(lang, "error", f"write failed: {exc}"))
            continue
        result.outcomes.append(
            LanguageOutcome(lang, "downloaded", cand.release or cand.provider.name, path)
        )


def _place_embedded(
    info: MovieInfo,
    options: RunOptions,
    downloaded: list[tuple[Language, bytes, SubtitleCandidate]],
    result: MovieResult,
    log: Logger,
) -> None:
    if not downloaded:
        return
    # Embedding rewrites the container once with all tracks. Write the subtitle
    # bytes to temp files first, mux, then clean them up.
    import tempfile

    tracks: list[SubtitleTrack] = []
    temp_files: list[str] = []
    try:
        for lang, data, cand in downloaded:
            fd, temp_path = tempfile.mkstemp(suffix=cand.subtitle_ext, prefix="subgenie_sub_")
            temp_files.append(temp_path)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            tracks.append(SubtitleTrack(
                path=temp_path, language=lang,
                forced=cand.forced, hearing_impaired=cand.hearing_impaired,
            ))
        try:
            out = embed_subtitles(info.path, tracks, keep_original=options.keep_original_on_embed)
            result.embedded_path = out
            for lang, _, cand in downloaded:
                result.outcomes.append(
                    LanguageOutcome(lang, "embedded", cand.release or cand.provider.name, out)
                )
        except EmbedError as exc:
            result.error = str(exc)
            log(f"  embed failed: {exc}")
            # Fall back to sidecars so the download isn't wasted.
            log("  falling back to sidecar files for this movie.")
            _place_sidecars(info, options, downloaded, result)
    finally:
        for temp_path in temp_files:
            try:
                os.remove(temp_path)
            except OSError:
                pass
