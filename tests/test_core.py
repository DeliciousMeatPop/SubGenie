"""Tests for the core orchestration using a fake provider (no network)."""

from subgenie import languages
from subgenie.config import ACTION_SIDECAR
from subgenie.core import RunOptions, best_candidate_per_language, process_movie
from subgenie.mediainfo import parse
from subgenie.providers.base import Provider, SubtitleCandidate, SubtitleQuery


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, candidates_by_lang, payloads=None):
        self._by_lang = candidates_by_lang
        self._payloads = payloads or {}

    def is_available(self):
        return True

    def search(self, query: SubtitleQuery):
        out = []
        for lang in query.languages:
            for cand in self._by_lang.get(lang.alpha3, []):
                cand.provider = self
                out.append(cand)
        return out

    def download(self, candidate):
        return self._payloads.get(candidate.language.alpha3, b"subtitle-bytes")


def _make_candidate(lang, **kwargs):
    return SubtitleCandidate(provider=None, language=lang, **kwargs)


def test_best_candidate_prefers_hash_match():
    en = languages.find("en")
    low = _make_candidate(en, downloads=1000, rating=9.0, hash_match=False)
    hashed = _make_candidate(en, downloads=1, rating=1.0, hash_match=True)
    best = best_candidate_per_language([low, hashed], RunOptions(languages=[en]))
    assert best["eng"] is hashed


def test_best_candidate_uses_downloads_without_hash():
    en = languages.find("en")
    a = _make_candidate(en, downloads=10, rating=5.0)
    b = _make_candidate(en, downloads=500, rating=5.0)
    best = best_candidate_per_language([a, b], RunOptions(languages=[en]))
    assert best["eng"] is b


def test_filters_exclude_hearing_impaired():
    en = languages.find("en")
    hi = _make_candidate(en, hearing_impaired=True)
    opts = RunOptions(languages=[en], hearing_impaired="exclude")
    best = best_candidate_per_language([hi], opts)
    assert best == {}


def test_process_movie_writes_sidecars(tmp_path):
    movie = tmp_path / "The Film (2020) 1080p.mkv"
    movie.write_bytes(b"x" * (300 * 1024))
    info = parse(str(movie))

    en = languages.find("en")
    es = languages.find("es")
    provider = FakeProvider({
        "eng": [_make_candidate(en, release="GROUP", downloads=100)],
        "spa": [_make_candidate(es, release="GRUPO", downloads=50)],
    }, payloads={"eng": b"english-sub", "spa": b"spanish-sub"})

    options = RunOptions(languages=[en, es], action=ACTION_SIDECAR)
    result = process_movie(info, options, [provider])

    statuses = {o.language.alpha2: o.status for o in result.outcomes}
    assert statuses == {"en": "downloaded", "es": "downloaded"}

    en_file = tmp_path / "The Film (2020) 1080p.en.srt"
    es_file = tmp_path / "The Film (2020) 1080p.es.srt"
    assert en_file.read_bytes() == b"english-sub"
    assert es_file.read_bytes() == b"spanish-sub"


def test_process_movie_reports_notfound(tmp_path):
    movie = tmp_path / "Obscure (1931).mkv"
    movie.write_bytes(b"x" * (300 * 1024))
    info = parse(str(movie))
    en = languages.find("en")
    provider = FakeProvider({})  # nothing found
    result = process_movie(info, RunOptions(languages=[en]), [provider])
    assert result.outcomes[0].status == "notfound"


def test_process_movie_skips_existing(tmp_path):
    movie = tmp_path / "Have It (2000).mkv"
    movie.write_bytes(b"x" * (300 * 1024))
    (tmp_path / "Have It (2000).en.srt").write_text("already here")
    info = parse(str(movie))
    en = languages.find("en")
    provider = FakeProvider({"eng": [_make_candidate(en)]})
    result = process_movie(info, RunOptions(languages=[en]), [provider])
    assert result.outcomes[0].status == "skipped"
    # Existing file untouched.
    assert (tmp_path / "Have It (2000).en.srt").read_text() == "already here"
