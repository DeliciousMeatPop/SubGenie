"""Turn a normal subtitle into a 3D-aware one.

A flat ``.srt`` rendered over a Side-by-Side (or Over-Under) 3D movie shows up
once, centered across the whole frame - straddling the seam between the two
eye-images. On a 3D display each eye then only sees half the text and it never
fuses. This module fixes that by rewriting the subtitle as an Advanced
SubStation Alpha (``.ass``) file that draws **one copy per eye**, positioned in
that eye's half of the frame and anamorphically scaled to match it:

  * **Side-by-Side (SBS/HSBS):** left copy centered in the left half, right copy
    in the right half. Half-SBS squeezes each eye horizontally, so the text is
    drawn at 50% X-scale to look correct after the display stretches it back.
  * **Over-Under (OU/HOU):** top copy in the top half, bottom copy in the
    bottom half; Half-OU squeezes vertically, so 50% Y-scale.

An optional ``disparity`` shifts the two copies horizontally to place the
subtitle in front of / behind the screen plane; 0 (the default) puts it right
at screen depth, which is the safe, comfortable choice.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Optional

# Canonical 3D tags (as produced by mediainfo.detect_3d) grouped by geometry.
_SBS_TAGS = {"SBS", "HSBS"}
_OU_TAGS = {"OU", "HOU"}
_HALF_TAGS = {"HSBS", "HOU"}          # anamorphically squeezed formats

DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080


@dataclass
class Layout:
    orientation: str      # "sbs" or "ou"
    squeeze: bool         # True for half formats (anamorphic)


def resolve_layout(three_d_format: Optional[str], width: int, height: int) -> Layout:
    """Decide SBS-vs-OU and half-vs-full from the tag, with an aspect fallback.

    When the filename only says a generic "3D" (no SBS/OU), we guess from the
    frame's aspect ratio: an unusually wide frame implies full SBS, an unusually
    tall one implies full OU; otherwise we assume Half-SBS, which is by far the
    most common layout for 3D rips.
    """
    tag = (three_d_format or "").upper()
    if tag in _SBS_TAGS:
        return Layout("sbs", tag in _HALF_TAGS)
    if tag in _OU_TAGS:
        return Layout("ou", tag in _HALF_TAGS)

    # Generic "3D" (or unknown): infer from aspect ratio.
    ratio = (width / height) if height else 1.78
    if ratio >= 2.6:
        return Layout("sbs", squeeze=False)   # full SBS (double-wide)
    if ratio <= 1.1:
        return Layout("ou", squeeze=False)    # full OU (double-tall)
    return Layout("sbs", squeeze=True)        # assume Half-SBS


@dataclass
class SrtEvent:
    start: str   # ASS time, e.g. "0:00:05.09"
    end: str
    text: str    # with \N line breaks, ASS-safe


_SRT_TIME = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)
_TAG = re.compile(r"<[^>]+>")


def _srt_ms_to_ass(h: str, m: str, s: str, ms: str) -> str:
    centis = int(round(int(ms.ljust(3, "0")[:3]) / 10.0))
    total_cs = centis
    ss = int(s)
    if total_cs >= 100:
        ss += total_cs // 100
        total_cs %= 100
    return f"{int(h)}:{int(m):02d}:{ss:02d}.{total_cs:02d}"


def parse_srt(text: str) -> list[SrtEvent]:
    """Parse SRT text into timed events. Tolerant of BOM, CRLF, stray blanks."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    events: list[SrtEvent] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln for ln in block.split("\n") if ln.strip() != ""]
        if not lines:
            continue
        # Find the timing line (skip an optional numeric index before it).
        timing_idx = None
        for i, line in enumerate(lines):
            if _SRT_TIME.search(line):
                timing_idx = i
                break
        if timing_idx is None:
            continue
        match = _SRT_TIME.search(lines[timing_idx])
        start = _srt_ms_to_ass(*match.group(1, 2, 3, 4))
        end = _srt_ms_to_ass(*match.group(5, 6, 7, 8))
        body_lines = lines[timing_idx + 1:]
        cleaned = _TAG.sub("", "\n".join(body_lines)).strip()
        if not cleaned:
            continue
        ass_text = cleaned.replace("\n", r"\N")
        events.append(SrtEvent(start, end, ass_text))
    return events


def video_resolution(path: str) -> tuple[int, int]:
    """Return (width, height) via ffprobe, or the 1080p default if unavailable."""
    from . import ffmpeg as ffmpeg_tools

    ffprobe = ffmpeg_tools.ffprobe_path()
    if not ffprobe:
        return DEFAULT_WIDTH, DEFAULT_HEIGHT
    cmd = [
        ffprobe, "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        path,
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout.strip()
        w_str, h_str = out.split("x")[:2]
        w, h = int(w_str), int(h_str)
        if w > 0 and h > 0:
            return w, h
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return DEFAULT_WIDTH, DEFAULT_HEIGHT


def _positions(layout: Layout, width: int, height: int, disparity: int):
    """Return ((x1,y1),(x2,y2), scale_override) for the two eye copies."""
    if layout.orientation == "sbs":
        y = int(height * 0.90)
        left = (int(width * 0.25) + disparity, y)
        right = (int(width * 0.75) - disparity, y)
        scale = r"\fscx50" if layout.squeeze else ""
        return left, right, scale
    # over-under
    x = int(width * 0.5)
    top = (x, int(height * 0.46))
    bottom = (x, int(height * 0.96))
    scale = r"\fscy50" if layout.squeeze else ""
    return top, bottom, scale


def _ass_header(width: int, height: int, font_size: int) -> str:
    return (
        "[Script Info]\n"
        "; Generated by SubtitleGenie - 3D (per-eye) subtitle\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,"
        "&H64000000,0,0,0,0,100,100,0,0,1,2,1,2,10,10,10,1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )


def convert_to_3d_ass(
    srt_text: str,
    three_d_format: Optional[str],
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    disparity: int = 0,
    font_size: Optional[int] = None,
) -> str:
    """Convert SRT text into a per-eye 3D ``.ass`` document (as a string)."""
    layout = resolve_layout(three_d_format, width, height)
    (x1, y1), (x2, y2), scale = _positions(layout, width, height, disparity)
    if font_size is None:
        font_size = max(24, int(height * 0.05))

    events = parse_srt(srt_text)
    lines = [_ass_header(width, height, font_size)]
    for ev in events:
        for (x, y) in ((x1, y1), (x2, y2)):
            override = f"{{\\an2\\pos({x},{y}){scale}}}"
            lines.append(
                f"Dialogue: 0,{ev.start},{ev.end},Default,,0,0,0,,{override}{ev.text}"
            )
    return "\n".join(lines) + "\n"


def convert_file_to_3d_ass(
    srt_path: str,
    three_d_format: Optional[str],
    *,
    movie_path: Optional[str] = None,
    disparity: int = 0,
) -> str:
    """Read an SRT file and write a sibling ``.ass`` 3D subtitle. Returns its path.

    Resolution is probed from ``movie_path`` when given (falling back to 1080p),
    so the per-eye positions match the actual frame.
    """
    import os

    with open(srt_path, "r", encoding="utf-8", errors="replace") as handle:
        srt_text = handle.read()

    width, height = (
        video_resolution(movie_path) if movie_path else (DEFAULT_WIDTH, DEFAULT_HEIGHT)
    )
    ass_text = convert_to_3d_ass(
        srt_text, three_d_format, width=width, height=height, disparity=disparity
    )
    ass_path = os.path.splitext(srt_path)[0] + ".ass"
    with open(ass_path, "w", encoding="utf-8") as handle:
        handle.write(ass_text)
    return ass_path
