"""Tests for language lookup and resolution."""

from subgenie import languages


def test_find_by_various_tokens():
    assert languages.find("en").name == "English"
    assert languages.find("EN").name == "English"
    assert languages.find("eng").name == "English"
    assert languages.find("english").name == "English"
    assert languages.find("English").name == "English"


def test_find_unknown_returns_none():
    assert languages.find("klingon") is None
    assert languages.find("") is None


def test_resolve_many_dedupes_and_preserves_order():
    found, unknown = languages.resolve_many(["es", "en", "spanish", "fr"])
    names = [l.name for l in found]
    # "es" and "spanish" are the same language -> deduped.
    assert names == ["Spanish", "English", "French"]
    assert unknown == []


def test_resolve_many_reports_unknown():
    found, unknown = languages.resolve_many(["en", "zzz", "de"])
    assert [l.alpha2 for l in found] == ["en", "de"]
    assert unknown == ["zzz"]


def test_resolve_all_expands_everything():
    found, unknown = languages.resolve_many(["all"])
    assert unknown == []
    assert len(found) == len(languages.all_languages())


def test_sidecar_code_prefers_alpha2():
    assert languages.find("en").sidecar_code == "en"


def test_brazilian_portuguese_distinct_from_portuguese():
    pt = languages.find("pt")
    pb = languages.find("pb")
    assert pt is not None and pb is not None
    assert pt.os_code == "pt-PT"
    assert pb.os_code == "pt-BR"
