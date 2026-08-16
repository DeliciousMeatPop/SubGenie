"""Tests for scripts/promote_changelog.py."""

import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "promote_changelog", os.path.join(ROOT, "scripts", "promote_changelog.py")
)
promote_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(promote_mod)
promote = promote_mod.promote

_CHANGELOG = """# Changelog

## [Unreleased]

### Added
- New feature A
- New feature B

## [0.1.0] - 2026-08-15

First public build.

[Unreleased]: https://example/compare/v0.1.0...HEAD
[0.1.0]: https://example/releases/tag/v0.1.0
"""


def test_promote_creates_version_section_and_clears_unreleased():
    new, changed = promote(_CHANGELOG, "0.2.0", "2026-09-01")
    assert changed is True
    # New dated section holds the moved content.
    assert "## [0.2.0] - 2026-09-01" in new
    assert "New feature A" in new
    # Unreleased still exists but no longer has the moved bullets.
    unreleased = new.split("## [0.2.0]")[0]
    assert "## [Unreleased]" in unreleased
    assert "New feature A" not in unreleased
    # Old version section untouched.
    assert "## [0.1.0] - 2026-08-15" in new


def test_promote_updates_reference_links():
    new, _ = promote(_CHANGELOG, "0.2.0", "2026-09-01")
    assert "[Unreleased]: https://github.com/DeliciousMeatPop/SubGenie/compare/v0.2.0...HEAD" in new
    assert "[0.2.0]: https://github.com/DeliciousMeatPop/SubGenie/releases/tag/v0.2.0" in new


def test_promote_is_idempotent_when_section_exists():
    once, changed1 = promote(_CHANGELOG, "0.2.0", "2026-09-01")
    twice, changed2 = promote(once, "0.2.0", "2026-09-01")
    assert changed1 is True
    assert changed2 is False
    assert twice == once


def test_promote_strips_leading_v():
    new, changed = promote(_CHANGELOG, "v0.2.0", "2026-09-01")
    assert changed is True
    assert "## [0.2.0] - 2026-09-01" in new


def test_promote_noop_when_unreleased_empty():
    empty = _CHANGELOG.replace(
        "### Added\n- New feature A\n- New feature B",
        "_Nothing yet._",
    )
    new, changed = promote(empty, "0.2.0", "2026-09-01")
    assert changed is False
    assert new == empty


def test_each_release_notes_are_disjoint_after_promotion():
    # Promote 0.2.0, then add new Unreleased content, promote 0.3.0. Each
    # version section must contain only its own changes.
    after_020, _ = promote(_CHANGELOG, "0.2.0", "2026-09-01")
    with_new = after_020.replace(
        "## [0.2.0]",
        "### Added\n- Feature C\n\n## [0.2.0]",
        1,
    )
    after_030, changed = promote(with_new, "0.3.0", "2026-10-01")
    assert changed is True
    section_030 = after_030.split("## [0.3.0]")[1].split("## [0.2.0]")[0]
    section_020 = after_030.split("## [0.2.0]")[1].split("## [0.1.0]")[0]
    assert "Feature C" in section_030 and "New feature A" not in section_030
    assert "New feature A" in section_020 and "Feature C" not in section_020
