"""Tests for the embed module's logic that don't require ffmpeg installed."""

import pytest

from subgenie import embed, languages
from subgenie.embed import EmbedError, SubtitleTrack, _subtitle_codec


def test_codec_selection():
    assert _subtitle_codec(".mkv") == "srt"
    assert _subtitle_codec(".MKV") == "srt"
    assert _subtitle_codec(".mp4") == "mov_text"
    assert _subtitle_codec(".m4v") == "mov_text"
    assert _subtitle_codec(".mov") == "mov_text"


def test_embed_raises_without_ffmpeg(monkeypatch, tmp_path):
    monkeypatch.setattr(embed, "ffmpeg_path", lambda: None)
    movie = tmp_path / "m.mkv"
    movie.write_bytes(b"x")
    track = SubtitleTrack(path=str(tmp_path / "s.srt"), language=languages.find("en"))
    with pytest.raises(EmbedError) as exc:
        embed.embed_subtitles(str(movie), [track])
    assert "ffmpeg" in str(exc.value).lower()


def test_embed_raises_with_no_tracks(monkeypatch, tmp_path):
    monkeypatch.setattr(embed, "ffmpeg_path", lambda: "/usr/bin/ffmpeg")
    movie = tmp_path / "m.mkv"
    movie.write_bytes(b"x")
    with pytest.raises(EmbedError):
        embed.embed_subtitles(str(movie), [])


def test_embedded_languages_empty_without_ffprobe(monkeypatch):
    monkeypatch.setattr(embed, "ffprobe_path", lambda: None)
    assert embed.embedded_languages("/whatever.mkv") == set()


def test_embed_command_shape(monkeypatch, tmp_path):
    """Verify the ffmpeg command is assembled correctly (without running it)."""
    captured = {}

    class Result:
        returncode = 0
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        # Simulate ffmpeg producing the temp output file.
        open(cmd[-1], "wb").close()
        return Result()

    monkeypatch.setattr(embed, "ffmpeg_path", lambda: "ffmpeg")
    monkeypatch.setattr(embed.subprocess, "run", fake_run)

    movie = tmp_path / "Film (2020).mkv"
    movie.write_bytes(b"original-container")
    sub = tmp_path / "s.srt"
    sub.write_text("1\n")

    track = SubtitleTrack(path=str(sub), language=languages.find("fr"), forced=True)
    out = embed.embed_subtitles(str(movie), [track])

    assert out == str(movie)
    cmd = captured["cmd"]
    assert cmd[0] == "ffmpeg"
    assert "-map" in cmd and "0" in cmd
    assert "language=fre" in cmd  # French alpha3
    # forced disposition present
    assert any(part == "forced" for part in cmd)
    assert "-c:s" in cmd and "srt" in cmd
