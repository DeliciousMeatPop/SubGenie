"""Tests for ffmpeg discovery, guidance, and opt-in install extraction."""

import io
import os
import tarfile
import zipfile

from subgenie import ffmpeg


def test_guidance_mentions_official_link_and_command():
    text = ffmpeg.guidance()
    assert ffmpeg.OFFICIAL_DOWNLOAD_URL in text
    assert "install-ffmpeg" in text


def test_find_prefers_path(monkeypatch):
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name: "/usr/bin/" + name)
    assert ffmpeg.find("ffmpeg") == "/usr/bin/ffmpeg"


def test_find_falls_back_to_local_install(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name: None)
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / ffmpeg._exe("ffmpeg")
    exe.write_bytes(b"#!/bin/true\n")
    os.chmod(exe, 0o755)
    monkeypatch.setattr(ffmpeg, "local_bin_dir", lambda: str(bindir))
    assert ffmpeg.find("ffmpeg") == str(exe)


def test_find_returns_none_when_absent(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda name: None)
    monkeypatch.setattr(ffmpeg, "local_bin_dir", lambda: str(tmp_path / "nope"))
    assert ffmpeg.find("ffmpeg") is None


def test_members_to_extract_picks_only_binaries(monkeypatch):
    monkeypatch.setattr(ffmpeg, "_wanted_basenames", lambda: {"ffmpeg", "ffprobe"})
    names = [
        "build/bin/ffmpeg",
        "build/bin/ffprobe",
        "build/bin/ffplay",
        "build/README.txt",
        "build/LICENSE",
    ]
    got = ffmpeg._members_to_extract(names)
    assert set(got) == {"ffmpeg", "ffprobe"}


def test_extract_from_zip(monkeypatch, tmp_path):
    # Force POSIX-style basenames regardless of host so the test is stable.
    monkeypatch.setattr(ffmpeg, "_wanted_basenames", lambda: {"ffmpeg", "ffprobe"})
    archive = tmp_path / "ffmpeg.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("ffmpeg-x/bin/ffmpeg", b"BIN1")
        zf.writestr("ffmpeg-x/bin/ffprobe", b"BIN2")
        zf.writestr("ffmpeg-x/README.txt", "docs")
    dest = tmp_path / "out"
    installed = ffmpeg._extract(str(archive), str(dest))
    assert sorted(os.path.basename(p) for p in installed) == ["ffmpeg", "ffprobe"]
    assert (dest / "ffmpeg").read_bytes() == b"BIN1"


def test_extract_from_tar_xz(monkeypatch, tmp_path):
    monkeypatch.setattr(ffmpeg, "_wanted_basenames", lambda: {"ffmpeg", "ffprobe"})
    archive = tmp_path / "ffmpeg.tar.xz"
    with tarfile.open(archive, "w:xz") as tf:
        for name, data in [("ffmpeg-x/ffmpeg", b"E1"), ("ffmpeg-x/ffprobe", b"E2")]:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    dest = tmp_path / "out"
    installed = ffmpeg._extract(str(archive), str(dest))
    assert len(installed) == 2
    if os.name != "nt":
        assert all(os.access(p, os.X_OK) for p in installed)
