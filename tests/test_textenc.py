"""Tests for subtitle encoding detection/decoding."""

from subgenie.textenc import decode_subtitle


def test_utf8_roundtrip():
    text = "Héllo — wörld, Ω"
    assert decode_subtitle(text.encode("utf-8")) == text


def test_utf8_bom_stripped():
    text = "hello"
    assert decode_subtitle("﻿".encode("utf-8") + b"hello") == text


def test_windows_1256_arabic_with_language_hint():
    # With the language hint, Arabic in Windows-1256 decodes correctly.
    arabic = "مرحبا بالعالم"
    out = decode_subtitle(arabic.encode("cp1256"), "ar")
    assert "�" not in out
    assert out == arabic


def test_windows_1251_cyrillic_with_language_hint():
    russian = "Привет мир, как дела сегодня"
    out = decode_subtitle(russian.encode("cp1251"), "ru")
    assert "�" not in out
    assert out == russian


def test_greek_with_language_hint():
    greek = "Γειά σου κόσμε"
    out = decode_subtitle(greek.encode("cp1253"), "el")
    assert out == greek


def test_utf8_wins_even_with_legacy_language_hint():
    # A UTF-8 file for a legacy-encoded language still decodes as UTF-8.
    arabic = "مرحبا"
    out = decode_subtitle(arabic.encode("utf-8"), "ar")
    assert out == arabic


def test_latin1_fallback_never_crashes():
    # Arbitrary bytes that aren't valid UTF-8 still decode to *something*.
    data = bytes(range(256))
    out = decode_subtitle(data)
    assert isinstance(out, str)


def test_empty_bytes():
    assert decode_subtitle(b"") == ""


def test_srt_cues_survive_decoding():
    srt = "1\r\n00:00:01,000 --> 00:00:03,000\nCafé\r\n".encode("cp1252")
    out = decode_subtitle(srt)
    assert "00:00:01,000 --> 00:00:03,000" in out
    assert "Café" in out
