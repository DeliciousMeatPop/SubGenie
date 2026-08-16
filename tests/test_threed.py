"""Tests for 3D subtitle conversion (SRT -> per-eye ASS)."""

from subgenie import threed

SAMPLE_SRT = """1
00:00:05,000 --> 00:00:07,500
Hello there.

2
00:00:08,100 --> 00:00:10,000
Line one
Line two
"""


def test_parse_srt_basic():
    events = threed.parse_srt(SAMPLE_SRT)
    assert len(events) == 2
    assert events[0].start == "0:00:05.00"
    assert events[0].end == "0:00:07.50"
    assert events[0].text == "Hello there."
    # Multi-line joined with ASS newline.
    assert events[1].text == r"Line one\NLine two"


def test_parse_srt_strips_html_and_bom():
    srt = "﻿1\n00:00:01,000 --> 00:00:02,000\n<i>Italic</i> word\n"
    events = threed.parse_srt(srt)
    assert events[0].text == "Italic word"


def test_resolve_layout_from_tags():
    assert threed.resolve_layout("HSBS", 1920, 1080) == threed.Layout("sbs", True)
    assert threed.resolve_layout("SBS", 1920, 1080) == threed.Layout("sbs", False)
    assert threed.resolve_layout("HOU", 1920, 1080) == threed.Layout("ou", True)
    assert threed.resolve_layout("OU", 1920, 1080) == threed.Layout("ou", False)


def test_resolve_layout_generic_defaults_to_half_sbs():
    # Generic "3D" with normal 16:9 frame -> Half-SBS assumption.
    assert threed.resolve_layout("3D", 1920, 1080) == threed.Layout("sbs", True)
    # Very wide frame -> full SBS.
    assert threed.resolve_layout(None, 3840, 1080) == threed.Layout("sbs", False)
    # Very tall frame -> full OU.
    assert threed.resolve_layout(None, 1920, 2160) == threed.Layout("ou", False)


def test_convert_hsbs_produces_two_positioned_copies():
    ass = threed.convert_to_3d_ass(SAMPLE_SRT, "HSBS", width=1920, height=1080)
    dialogues = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    # 2 events x 2 eyes = 4 dialogue lines.
    assert len(dialogues) == 4
    # Left eye centered at 25% (480), right at 75% (1440); half-SBS squeezes X.
    assert r"\pos(480," in ass
    assert r"\pos(1440," in ass
    assert r"\fscx50" in ass
    assert r"\fscy" not in ass


def test_convert_hou_uses_vertical_scale_and_stacking():
    ass = threed.convert_to_3d_ass(SAMPLE_SRT, "HOU", width=1920, height=1080)
    assert r"\fscy50" in ass
    assert r"\fscx" not in ass
    # Both copies horizontally centered at 960.
    assert ass.count(r"\pos(960,") == 4


def test_full_sbs_has_no_squeeze():
    ass = threed.convert_to_3d_ass(SAMPLE_SRT, "SBS", width=3840, height=1080)
    assert r"\fscx" not in ass
    assert r"\pos(960," in ass    # 25% of 3840
    assert r"\pos(2880," in ass   # 75% of 3840


def test_disparity_shifts_eyes():
    ass = threed.convert_to_3d_ass(SAMPLE_SRT, "HSBS", width=1920, height=1080, disparity=20)
    assert r"\pos(500," in ass    # 480 + 20
    assert r"\pos(1420," in ass   # 1440 - 20


def test_header_has_playres():
    ass = threed.convert_to_3d_ass(SAMPLE_SRT, "HSBS", width=1920, height=1080)
    assert "PlayResX: 1920" in ass
    assert "PlayResY: 1080" in ass
    assert "[Events]" in ass


import re


def _sbs_y(ass):
    ys = {int(m) for m in re.findall(r"\\pos\(\d+,(\d+)\)", ass)}
    assert len(ys) == 1  # both eyes share one vertical position for SBS
    return ys.pop()


def test_sbs_sits_near_bottom_of_full_frame_without_band():
    ass = threed.convert_to_3d_ass(SAMPLE_SRT, "SBS", width=1920, height=1080)
    y = _sbs_y(ass)
    # No band -> near the bottom of the whole frame (but not off the edge).
    assert 0.88 * 1080 <= y <= 1080


def test_band_places_subs_at_bottom_of_picture_not_frame():
    # Cinemascope picture occupies rows 140..940 of a 1080 frame.
    ass = threed.convert_to_3d_ass(
        SAMPLE_SRT, "SBS", width=1920, height=1080, band=(140, 940)
    )
    y = _sbs_y(ass)
    # Just above the picture bottom (940), and inside the picture — not down in
    # the black bar (which is where 0.90*1080=972 would land).
    assert 880 <= y <= 940
    assert y < 972


def test_over_under_band_stacks_within_each_half():
    ass = threed.convert_to_3d_ass(
        SAMPLE_SRT, "HOU", width=1920, height=1080, band=(100, 1000)
    )
    ys = sorted(int(m) for m in re.findall(r"\\pos\(\d+,(\d+)\)", ass))
    # Two distinct heights: bottom of the top picture (~mid) and bottom overall.
    top_eye, bottom_eye = ys[0], ys[-1]
    assert top_eye < 550 < bottom_eye     # top copy above the midline, bottom below
