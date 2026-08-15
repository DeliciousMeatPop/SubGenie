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


def test_extract_changelog_finds_known_version():
    body = brn.extract_changelog("0.1.0")
    assert "First public build" in body
    # Stops before the next heading (no Unreleased content leaking in).
    assert "Unreleased" not in body


def test_extract_changelog_missing_version_falls_back():
    body = brn.extract_changelog("99.99.99")
    assert "No CHANGELOG entry" in body


def test_render_v010_uses_special_file_and_injects_changelog():
    out = brn.render("v0.1.0")
    assert "the first one" in out.lower()          # from the special file
    assert "First public build" in out             # injected changelog
    assert "{{" not in out                          # all placeholders resolved


def test_render_unknown_version_uses_template():
    out = brn.render("v3.1.4")
    assert "SubtitleGenie 3.1.4" in out
    assert "Download & run" in out                  # from the default template
    assert "{{" not in out
