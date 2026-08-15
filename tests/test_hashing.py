"""Tests for the OpenSubtitles hash."""

import os
import struct

from subgenie import hashing


def _write_file(path, size, fill=b"\x00"):
    with open(path, "wb") as handle:
        handle.write(fill * size)


def test_too_small_returns_none(tmp_path):
    path = tmp_path / "tiny.mkv"
    _write_file(str(path), 1000)
    assert hashing.compute_hash(str(path)) is None


def test_missing_file_returns_none(tmp_path):
    assert hashing.compute_hash(str(tmp_path / "nope.mkv")) is None


def test_hash_of_all_zero_file_is_just_the_size(tmp_path):
    # With an all-zero file, the chunk sums add nothing, so the hash equals the
    # file size rendered as 16 hex digits.
    size = 256 * 1024  # 256 KiB, comfortably above the 128 KiB minimum
    path = tmp_path / "zeros.mkv"
    _write_file(str(path), size)
    assert hashing.compute_hash(str(path)) == f"{size:016x}"


def test_hash_is_deterministic_and_16_hex_chars(tmp_path):
    path = tmp_path / "movie.mkv"
    data = bytes((i * 7) % 256 for i in range(300 * 1024))
    with open(str(path), "wb") as handle:
        handle.write(data)
    first = hashing.compute_hash(str(path))
    second = hashing.compute_hash(str(path))
    assert first == second
    assert first is not None
    assert len(first) == 16
    int(first, 16)  # parses as hex


def test_known_value_matches_reference_algorithm(tmp_path):
    # Reimplement the reference algorithm independently and compare.
    size = 200 * 1024
    data = os.urandom(size)
    path = tmp_path / "rand.mkv"
    with open(str(path), "wb") as handle:
        handle.write(data)

    mask = 0xFFFFFFFFFFFFFFFF
    expected = size
    for chunk in (data[:65536], data[-65536:]):
        for offset in range(0, 65536, 8):
            (value,) = struct.unpack("<q", chunk[offset:offset + 8])
            expected = (expected + value) & mask

    assert hashing.compute_hash(str(path)) == f"{expected:016x}"
