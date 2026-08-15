"""OpenSubtitles file-hash computation.

The hash is size + a checksum of the first and last 64 KiB of the file. It lets
OpenSubtitles return a subtitle that is frame-accurately synced to *this exact
release*, without knowing the movie's title. This is the single most reliable
way to get a subtitle that actually lines up, which matters doubly for 3D
releases whose runtimes often differ from the 2D version.

Reference: https://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes
"""

from __future__ import annotations

import os
import struct
from typing import Optional

_CHUNK = 64 * 1024  # 64 KiB read from head and tail
_LONGLONG = "<q"
_LONGLONG_SIZE = struct.calcsize(_LONGLONG)
_MASK = 0xFFFFFFFFFFFFFFFF


def compute_hash(path: str) -> Optional[str]:
    """Return the 16-char lowercase hex OpenSubtitles hash, or ``None``.

    Returns ``None`` (rather than raising) when the file is smaller than
    128 KiB — such files can't be hashed by this scheme, and callers should
    simply fall back to name-based search.
    """
    try:
        filesize = os.path.getsize(path)
    except OSError:
        return None

    if filesize < _CHUNK * 2:
        return None

    hash_value = filesize
    try:
        with open(path, "rb") as handle:
            hash_value = _accumulate(handle, hash_value)
            handle.seek(max(0, filesize - _CHUNK), os.SEEK_SET)
            hash_value = _accumulate(handle, hash_value)
    except OSError:
        return None

    return f"{hash_value & _MASK:016x}"


def _accumulate(handle, hash_value: int) -> int:
    """Fold one 64 KiB chunk (as little-endian int64s) into the running hash."""
    buffer = handle.read(_CHUNK)
    for offset in range(0, len(buffer) - _LONGLONG_SIZE + 1, _LONGLONG_SIZE):
        (value,) = struct.unpack(_LONGLONG, buffer[offset : offset + _LONGLONG_SIZE])
        hash_value = (hash_value + value) & _MASK
    return hash_value
