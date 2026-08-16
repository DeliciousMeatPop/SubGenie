"""Tests for subtitle timing sync (the pure, dependency-free parts)."""

from subgenie import sync

_SRT = """1
00:00:01,000 --> 00:00:03,500
First line.

2
00:01:10,250 --> 00:01:12,000
Second line.
"""


def test_shift_forward():
    out = sync.shift_srt(_SRT, 2.0)
    assert "00:00:03,000 --> 00:00:05,500" in out
    assert "00:01:12,250 --> 00:01:14,000" in out


def test_shift_backward():
    out = sync.shift_srt(_SRT, -1.0)
    assert "00:00:00,000 --> 00:00:02,500" in out


def test_shift_clamps_at_zero():
    # Shifting further back than the first cue can't go negative.
    out = sync.shift_srt(_SRT, -5.0)
    assert "00:00:00,000 -->" in out


def test_zero_offset_is_noop():
    assert sync.shift_srt(_SRT, 0.0) == _SRT


def test_fractional_offset():
    out = sync.shift_srt(_SRT, 0.5)
    assert "00:00:01,500 --> 00:00:04,000" in out


def test_autosync_returns_none_without_ffsubsync(monkeypatch):
    monkeypatch.setattr(sync.shutil, "which", lambda name: None)
    assert sync.autosync("/movie.mkv", _SRT) is None
    assert sync.autosync_available() is False
