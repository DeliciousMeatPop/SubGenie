"""Tests for the self-update checker (no real network)."""

import os

from subgenie import updater
from subgenie.updater import Asset, Release


def test_parse_version_variants():
    assert updater.parse_version("v1.2.3") == (1, 2, 3)
    assert updater.parse_version("1.2") == (1, 2)
    assert updater.parse_version("2.0.0-rc1") == (2, 0, 0)
    assert updater.parse_version("") == (0,)


def test_is_newer():
    assert updater.is_newer("0.2.0", "0.1.0")
    assert updater.is_newer("1.0.0", "0.9.9")
    assert not updater.is_newer("0.1.0", "0.1.0")
    assert not updater.is_newer("0.1.0", "0.2.0")
    # A pre-release of the same base version isn't "newer" than the release.
    assert not updater.is_newer("1.0.0-rc1", "1.0.0")


def test_pick_asset_matches_platform():
    assets = [
        Asset("SubtitleGenie-0.2.0-linux-x64.tar.gz", "http://x/linux"),
        Asset("SubtitleGenie-0.2.0-windows-x64.zip", "http://x/win"),
        Asset("SubtitleGenie-0.2.0-macos-arm64.tar.gz", "http://x/mac"),
    ]
    assert updater.pick_asset(assets, "windows").url == "http://x/win"
    assert updater.pick_asset(assets, "macos").url == "http://x/mac"
    assert updater.pick_asset(assets, "linux").url == "http://x/linux"
    assert updater.pick_asset(assets, "solaris") is None


def test_platform_key_is_known():
    assert updater.platform_key() in {"windows", "macos", "linux"}


def test_check_for_update_returns_release_when_newer(monkeypatch):
    rel = Release(tag="v9.9.9", version="9.9.9", url="http://x", assets=[])
    monkeypatch.setattr(updater, "fetch_latest", lambda *a, **k: rel)
    assert updater.check_for_update("0.1.0") is rel


def test_check_for_update_none_when_current(monkeypatch):
    rel = Release(tag="v0.1.0", version="0.1.0", url="http://x", assets=[])
    monkeypatch.setattr(updater, "fetch_latest", lambda *a, **k: rel)
    assert updater.check_for_update("0.1.0") is None


def test_check_for_update_none_on_fetch_failure(monkeypatch):
    monkeypatch.setattr(updater, "fetch_latest", lambda *a, **k: None)
    assert updater.check_for_update("0.1.0") is None


class _FakeResponse:
    def __init__(self, chunks, headers=None):
        self._chunks = chunks
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size=0):
        yield from self._chunks


def test_download_asset_writes_file(monkeypatch, tmp_path):
    class FakeRequests:
        RequestException = Exception

        def get(self, url, headers=None, stream=False, timeout=0):
            return _FakeResponse([b"abc", b"def"], {"Content-Length": "6"})

    monkeypatch.setattr(updater, "requests", FakeRequests())
    asset = Asset("SubtitleGenie-1.0.0-linux-x64.tar.gz", "http://x/file")
    seen = []
    path = updater.download_asset(asset, str(tmp_path), progress=lambda d, t: seen.append((d, t)))
    assert path.endswith("SubtitleGenie-1.0.0-linux-x64.tar.gz")
    with open(path, "rb") as handle:
        assert handle.read() == b"abcdef"
    assert seen[-1] == (6, 6)


def test_current_binary_none_from_source(monkeypatch):
    # Not frozen -> no binary to sit beside.
    monkeypatch.delattr(updater.sys, "frozen", raising=False)
    assert updater.current_binary() is None


def test_find_binary_member_skips_docs():
    names = [
        "SubtitleGenie-0.2.0-win-x64/README.md",
        "SubtitleGenie-0.2.0-win-x64/CHANGELOG.md",
        "SubtitleGenie-0.2.0-win-x64/SubtitleGenie_win_v0.2.0.exe",
    ]
    assert updater._find_binary_member(names).endswith("SubtitleGenie_win_v0.2.0.exe")


def test_extract_binary_from_zip(tmp_path):
    import zipfile
    archive = tmp_path / "SubtitleGenie-0.2.0-win-x64.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("SubtitleGenie-0.2.0-win-x64/README.md", "readme")
        zf.writestr("SubtitleGenie-0.2.0-win-x64/SubtitleGenie_win_v0.2.0.exe", b"MZbinary")
    dest = tmp_path / "install"
    out = updater.extract_binary(str(archive), str(dest))
    assert out == str(dest / "SubtitleGenie_win_v0.2.0.exe")
    assert (dest / "SubtitleGenie_win_v0.2.0.exe").read_bytes() == b"MZbinary"
    # README must not be extracted.
    assert not (dest / "README.md").exists()


def test_extract_binary_from_targz(tmp_path):
    import io
    import tarfile
    archive = tmp_path / "SubtitleGenie-0.2.0-linux-x64.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        data = b"\x7fELFbinary"
        info = tarfile.TarInfo("SubtitleGenie-0.2.0-linux-x64/SubtitleGenie_linux_v0.2.0")
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    dest = tmp_path / "install"
    out = updater.extract_binary(str(archive), str(dest))
    assert out.endswith("SubtitleGenie_linux_v0.2.0")
    assert (dest / "SubtitleGenie_linux_v0.2.0").read_bytes() == b"\x7fELFbinary"
    # Executable bit set on POSIX.
    if os.name != "nt":
        assert os.access(out, os.X_OK)


def test_extract_binary_returns_none_when_no_binary(tmp_path):
    import zipfile
    archive = tmp_path / "empty.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("folder/README.md", "just docs")
    assert updater.extract_binary(str(archive), str(tmp_path / "out")) is None


def test_cleanup_previous_binary_deletes_old(monkeypatch, tmp_path):
    import time
    old = tmp_path / "SubtitleGenie_win_v0.0.1.exe"
    old.write_bytes(b"old")
    monkeypatch.setenv(updater.CLEANUP_ENV, str(old))
    monkeypatch.setattr(updater, "current_binary", lambda: None)  # not frozen
    updater.cleanup_previous_binary()
    for _ in range(20):
        if not old.exists():
            break
        time.sleep(0.05)
    assert not old.exists()


def test_cleanup_previous_binary_noop_without_env(monkeypatch):
    monkeypatch.delenv(updater.CLEANUP_ENV, raising=False)
    # Should simply return without error.
    updater.cleanup_previous_binary()


def test_cleanup_never_deletes_self(monkeypatch, tmp_path):
    import time
    me = tmp_path / "me.exe"
    me.write_bytes(b"self")
    monkeypatch.setenv(updater.CLEANUP_ENV, str(me))
    monkeypatch.setattr(updater, "current_binary", lambda: str(me))
    updater.cleanup_previous_binary()
    time.sleep(0.2)
    assert me.exists()  # never removed itself
