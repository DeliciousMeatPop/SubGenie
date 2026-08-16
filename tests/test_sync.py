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


def test_autosync_unavailable_without_ffsubsync_or_ffmpeg(monkeypatch):
    monkeypatch.setattr(sync, "_ffsubsync_available", lambda: False)
    monkeypatch.setattr(sync, "_ffmpeg_available", lambda: False)
    assert sync.autosync_available() is False


def test_autosync_available_with_ffmpeg_only(monkeypatch):
    # Built-in engine uses ffmpeg, so ffmpeg alone makes auto-sync available.
    monkeypatch.setattr(sync, "_ffsubsync_available", lambda: False)
    monkeypatch.setattr(sync, "_ffmpeg_available", lambda: True)
    assert sync.autosync_available() is True


def test_autosync_falls_back_to_builtin(monkeypatch):
    # No ffsubsync -> autosync should try the built-in engine.
    monkeypatch.setattr(sync, "_ffsubsync", lambda *a, **k: None)
    called = {}

    def fake_builtin(movie, text, log=None):
        called["yes"] = True
        return text

    monkeypatch.setattr(sync, "builtin_autosync", fake_builtin)
    assert sync.autosync("/movie.mkv", _SRT) == _SRT
    assert called.get("yes")


def test_srt_intervals_parsing():
    ivals = sync._srt_intervals(_SRT)
    assert ivals[0] == (1.0, 3.5)
    assert ivals[1] == (70.25, 72.0)


def test_total_overlap():
    a = [(0.0, 10.0), (20.0, 30.0)]
    b = [(5.0, 25.0)]
    # overlap: 5..10 (5s) + 20..25 (5s) = 10s
    assert sync._total_overlap(a, b) == 10.0


def test_best_lag_recovers_offset():
    # "Speech" bursts; subtitle cues are the same but 5s late.
    speech = [(10.0, 13.0), (22.0, 26.0), (40.0, 44.0), (52.0, 55.0)]
    subs = [(s + 5.0, e + 5.0) for s, e in speech]
    lag, score = sync._best_lag(speech, subs, max_lag=30.0, coarse=0.5, fine=0.1)
    assert abs(lag - (-5.0)) < 0.2      # recovers the -5s shift
    assert score > 0


def test_builtin_autosync_none_without_speech(monkeypatch):
    monkeypatch.setattr(sync, "_speech_intervals", lambda p, log=None: None)
    assert sync.builtin_autosync("/movie.mkv", _SRT) is None


def test_builtin_autosync_shifts_using_detected_speech(monkeypatch):
    # Real cues at 1..3 and 70.25..72; pretend speech is 5s earlier.
    monkeypatch.setattr(
        sync, "_speech_intervals",
        lambda p, log=None: [(-4.0, -2.0), (65.25, 67.0)],
    )
    out = sync.builtin_autosync("/movie.mkv", _SRT)
    assert out is not None
    # First cue should have moved ~5s earlier (from 00:00:01 toward negative→clamped).
    assert "00:01:05,250" in out or "00:01:05" in out   # 70.25 - 5 = 65.25s = 01:05.25
