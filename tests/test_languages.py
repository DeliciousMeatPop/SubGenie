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


def test_resolve_common_expands_to_preset():
    found, unknown = languages.resolve_many(["common"])
    assert unknown == []
    codes = [l.sidecar_code for l in found]
    # The preset the user asked for: English, both Spanishes, French, German, ...
    assert "en" in codes and "fr" in codes and "de" in codes
    assert "es" in codes and "ea" in codes          # Spain + Latin American Spanish
    assert "pt" in codes and "pb" in codes           # European + Brazilian Portuguese
    # A curated subset, not everything.
    assert 0 < len(found) < len(languages.all_languages())


def test_common_case_insensitive_and_dedupes_with_extra():
    found, _ = languages.resolve_many(["COMMON", "en"])
    codes = [l.sidecar_code for l in found]
    assert codes.count("en") == 1                     # 'en' already in common, deduped


def test_sidecar_code_prefers_alpha2():
    assert languages.find("en").sidecar_code == "en"


def test_brazilian_portuguese_distinct_from_portuguese():
    pt = languages.find("pt")
    pb = languages.find("pb")
    assert pt is not None and pb is not None
    assert pt.os_code == "pt-PT"
    assert pb.os_code == "pt-BR"
