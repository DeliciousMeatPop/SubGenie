"""Tests for scripts/stamp_version.py (the release version stamper)."""

import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SPEC = importlib.util.spec_from_file_location(
    "stamp_version", os.path.join(ROOT, "scripts", "stamp_version.py")
)
stamp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(stamp)


def _write_init(tmp_path, version="0.1.0"):
    init = tmp_path / "__init__.py"
    init.write_text(
        f'"""doc."""\n\n__version__ = "{version}"\n__app_name__ = "SubtitleGenie"\n',
        encoding="utf-8",
    )
    return init


def test_stamps_plain_version(tmp_path, monkeypatch):
    init = _write_init(tmp_path)
    monkeypatch.setattr(stamp, "INIT", init)
    assert stamp.main(["stamp", "0.0.3"]) == 0
    assert '__version__ = "0.0.3"' in init.read_text()
    # Other lines untouched.
    assert '__app_name__ = "SubtitleGenie"' in init.read_text()


def test_strips_leading_v(tmp_path, monkeypatch):
    init = _write_init(tmp_path)
    monkeypatch.setattr(stamp, "INIT", init)
    assert stamp.main(["stamp", "v1.2.3"]) == 0
    assert '__version__ = "1.2.3"' in init.read_text()


def test_missing_arg_returns_error(tmp_path, monkeypatch):
    init = _write_init(tmp_path)
    monkeypatch.setattr(stamp, "INIT", init)
    assert stamp.main(["stamp"]) == 2


def test_no_version_line_returns_error(tmp_path, monkeypatch):
    init = tmp_path / "__init__.py"
    init.write_text("# no version here\n", encoding="utf-8")
    monkeypatch.setattr(stamp, "INIT", init)
    assert stamp.main(["stamp", "0.0.3"]) == 1
