"""Tests for the embed module's logic that don't require ffmpeg installed."""

import pytest

from subgenie import embed, languages
from subgenie.embed import EmbedError, SubtitleTrack, _added_subtitle_codec


def test_added_codec_selection():
    # MKV copies our subs in as-is (ass/srt native); MP4 needs mov_text.
    assert _added_subtitle_codec(".mkv") == "copy"
    assert _added_subtitle_codec(".MKV") == "copy"
    assert _added_subtitle_codec(".mp4") == "mov_text"
    assert _added_subtitle_codec(".m4v") == "mov_text"
    assert _added_subtitle_codec(".mov") == "mov_text"


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


def _run_capture(monkeypatch, movie, tracks, offset=0):
    """Run embed_subtitles with ffmpeg mocked; return the captured argv."""
    captured = {}

    class Result:
        returncode = 0
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        open(cmd[-1], "wb").close()  # simulate ffmpeg making the temp output
        return Result()

    monkeypatch.setattr(embed, "ffmpeg_path", lambda: "ffmpeg")
    monkeypatch.setattr(embed, "subtitle_stream_count", lambda p: offset)
    monkeypatch.setattr(embed.subprocess, "run", fake_run)
    embed.embed_subtitles(str(movie), tracks)
    return captured["cmd"]


def test_embed_command_shape_mkv_copies_and_no_global_cs(monkeypatch, tmp_path):
    movie = tmp_path / "Film (2020).mkv"
    movie.write_bytes(b"container")
    sub = tmp_path / "s.srt"
    sub.write_text("1\n")
    track = SubtitleTrack(path=str(sub), language=languages.find("fr"), forced=True)

    cmd = _run_capture(monkeypatch, movie, [track], offset=0)
    assert cmd[0] == "ffmpeg"
    assert "-map" in cmd and "0" in cmd
    # Everything copied; no global "-c:s" that would transcode existing subs.
    assert "-c" in cmd and "copy" in cmd
    assert "-c:s" not in cmd
    # Metadata/disposition target our added stream at index 0.
    assert "-metadata:s:s:0" in cmd
    assert "language=fre" in cmd
    assert "-disposition:s:0" in cmd and "forced" in cmd


def test_embed_offsets_metadata_past_existing_subs(monkeypatch, tmp_path):
    """With existing subs in the movie, our tracks are addressed at the offset."""
    movie = tmp_path / "Movie HSBS.mkv"
    movie.write_bytes(b"container")
    a = tmp_path / "a.ass"; a.write_text("x")
    b = tmp_path / "b.ass"; b.write_text("x")
    tracks = [
        SubtitleTrack(path=str(a), language=languages.find("de")),
        SubtitleTrack(path=str(b), language=languages.find("ja")),
    ]
    # Pretend the movie already has 2 subtitle streams (e.g. PGS en/es).
    cmd = _run_capture(monkeypatch, movie, tracks, offset=2)
    # Our two subs land at output subtitle indices 2 and 3, not 0 and 1.
    assert "-metadata:s:s:2" in cmd and "language=ger" in cmd
    assert "-metadata:s:s:3" in cmd and "language=jpn" in cmd
    assert "-metadata:s:s:0" not in cmd  # never touches the movie's own subs


def test_embed_mp4_converts_added_to_mov_text(monkeypatch, tmp_path):
    movie = tmp_path / "Film.mp4"
    movie.write_bytes(b"container")
    sub = tmp_path / "s.srt"
    sub.write_text("1\n")
    track = SubtitleTrack(path=str(sub), language=languages.find("en"))
    cmd = _run_capture(monkeypatch, movie, [track], offset=0)
    # MP4 needs the added text sub converted, but only for our stream index.
    assert "-c:s:0" in cmd and "mov_text" in cmd
