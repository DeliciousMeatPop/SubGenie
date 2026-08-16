"""Tests for the release-notes generator (scripts/build_release_notes.py)."""

import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "build_release_notes", os.path.join(ROOT, "scripts", "build_release_notes.py")
)
brn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(brn)


def test_normalize_adds_v_prefix():
    assert brn.normalize("0.1.0") == ("v0.1.0", "0.1.0")
    assert brn.normalize("v0.2.0") == ("v0.2.0", "0.2.0")


_FIXTURE = """# Changelog

## [Unreleased]

### Added
- Unreleased line A
- Unreleased line B

## [0.2.0] - 2026-09-01

### Added
- Version 0.2.0 note

## [0.1.0] - 2026-08-15

First public build.

[Unreleased]: https://example/compare
[0.1.0]: https://example/tag
"""

_EMPTY_UNRELEASED = """# Changelog

## [Unreleased]

### Added
- _Nothing yet._

## [0.1.0] - 2026-08-15

First public build.
"""


def _patch_changelog(monkeypatch, tmp_path, text):
    path = tmp_path / "CHANGELOG.md"
    path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(brn, "CHANGELOG", str(path))


def test_extract_changelog_finds_known_version(monkeypatch, tmp_path):
    _patch_changelog(monkeypatch, tmp_path, _FIXTURE)
    body = brn.extract_changelog("0.2.0")
    assert "Version 0.2.0 note" in body
    # Stops before the next heading (no other sections leaking in).
    assert "Unreleased line" not in body
    assert "First public build" not in body


def test_extract_changelog_missing_version_falls_back_to_unreleased(monkeypatch, tmp_path):
    _patch_changelog(monkeypatch, tmp_path, _FIXTURE)
    body = brn.extract_changelog("99.99.99")
    assert "Unreleased line A" in body
    assert "Unreleased line B" in body


def test_extract_changelog_placeholder_when_unreleased_empty(monkeypatch, tmp_path):
    _patch_changelog(monkeypatch, tmp_path, _EMPTY_UNRELEASED)
    body = brn.extract_changelog("99.99.99")
    assert "No CHANGELOG entry" in body


def test_exact_version_wins_over_unreleased(monkeypatch, tmp_path):
    _patch_changelog(monkeypatch, tmp_path, _FIXTURE)
    body = brn.extract_changelog("0.1.0")
    assert "First public build" in body
    assert "Unreleased line" not in body


def test_render_v010_uses_special_file_and_injects_changelog():
    out = brn.render("v0.1.0")
    assert "the first one" in out.lower()          # from the special file
    assert "First public build" in out             # injected changelog
    assert "{{" not in out                          # all placeholders resolved


def test_render_unknown_version_uses_template():
    out = brn.render("v3.1.4")
    assert "3.1.4" in out                            # {{VERSION}} substituted
    assert "Download & run" in out                  # from the default template
    assert "{{" not in out
