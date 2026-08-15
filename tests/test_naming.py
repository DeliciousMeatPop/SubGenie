"""Tests for sidecar filename construction."""

from subgenie import languages, naming
from subgenie.mediainfo import parse


def _info(tmp_path, name="The Movie (2019).mkv"):
    p = tmp_path / name
    p.write_bytes(b"x")
    return parse(str(p))


def test_basic_sidecar_name(tmp_path):
    info = _info(tmp_path)
    en = languages.find("en")
    name = naming.sidecar_filename(info, en)
    assert name == "The Movie (2019).en.srt"


def test_forced_and_sdh_flags(tmp_path):
    info = _info(tmp_path)
    en = languages.find("en")
    name = naming.sidecar_filename(info, en, forced=True, hearing_impaired=True)
    assert name == "The Movie (2019).en.forced.sdh.srt"


def test_3d_tag_preserved_in_basename(tmp_path):
    info = _info(tmp_path, "Avatar (2009) 3D HSBS.mkv")
    en = languages.find("en")
    name = naming.sidecar_filename(info, en)
    assert name.startswith("Avatar (2009) 3D HSBS.")
    assert name.endswith(".en.srt")


def test_sidecar_path_avoids_collision(tmp_path):
    info = _info(tmp_path)
    en = languages.find("en")
    first = naming.sidecar_path(info, en)
    # Create it, then ask again -> should get a .2 variant.
    with open(first, "w") as handle:
        handle.write("x")
    second = naming.sidecar_path(info, en)
    assert second != first
    assert ".2.srt" in second


def test_sidecar_path_overwrite_returns_canonical(tmp_path):
    info = _info(tmp_path)
    en = languages.find("en")
    first = naming.sidecar_path(info, en)
    with open(first, "w") as handle:
        handle.write("x")
    again = naming.sidecar_path(info, en, overwrite=True)
    assert again == first
