"""Tests for filename parsing and 3D detection."""

import os

from subgenie import mediainfo


def test_parse_scene_style_name():
    info = mediainfo.parse("/movies/The.Matrix.1999.1080p.BluRay.x264-GROUP.mkv")
    assert info.title == "The Matrix"
    assert info.year == 1999
    assert info.is_3d is False
    assert info.extension == ".mkv"


def test_parse_plain_name_with_spaces():
    info = mediainfo.parse("/movies/Inception (2010).mp4")
    assert info.title == "Inception"
    assert info.year == 2010


def test_detect_3d_hsbs():
    info = mediainfo.parse("/m/Avatar.2009.1080p.BluRay.Half-SBS.x264.mkv")
    assert info.is_3d is True
    assert info.three_d_format == "HSBS"


def test_detect_3d_plain_tag():
    is_3d, fmt = mediainfo.detect_3d("Gravity 2013 3D 1080p")
    assert is_3d is True
    assert fmt == "3D"


def test_detect_over_under():
    is_3d, fmt = mediainfo.detect_3d("Movie.2015.1080p.HOU.mkv")
    assert is_3d is True
    assert fmt == "HOU"


def test_no_year_falls_back_to_stop_token():
    info = mediainfo.parse("/m/Some Movie 1080p BluRay.mkv")
    assert info.title == "Some Movie"
    assert info.year is None


def test_is_video_file():
    assert mediainfo.is_video_file("a.mkv")
    assert mediainfo.is_video_file("A.MP4")
    assert not mediainfo.is_video_file("a.srt")
    assert not mediainfo.is_video_file("a.txt")


def test_existing_sidecar_languages(tmp_path):
    movie = tmp_path / "The Film (2020).mkv"
    movie.write_bytes(b"x")
    (tmp_path / "The Film (2020).en.srt").write_text("1")
    (tmp_path / "The Film (2020).es.forced.srt").write_text("1")
    (tmp_path / "Unrelated.fr.srt").write_text("1")

    info = mediainfo.parse(str(movie))
    langs = mediainfo.existing_sidecar_languages(info)
    assert "en" in langs
    assert "es" in langs
    assert "fr" not in langs
