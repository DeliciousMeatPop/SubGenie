"""Persistent settings, including per-decision "ask or just do it" policies.

The whole point of this module: let the user decide, once, how hands-on they
want to be. Every interactive decision (which languages, sidecar vs embed,
2D vs 3D, whether to overwrite) has:

  * a stored **default** value, and
  * an **ask policy** (``ask`` or ``never``) saying whether SubtitleGenie should
    stop and ask, or silently use that default.

A single global **mode** sits on top:
  * ``always`` - ask every question that has a value to choose (maximally
    interactive),
  * ``smart``  - honor each decision's own ask policy (the default),
  * ``never``  - never ask anything; use defaults everywhere ("drop and go").

Config lives in the platform's standard config dir and is plain JSON so it's
easy to hand-edit.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any


# ---- where the config file lives ------------------------------------------

def config_dir() -> str:
    """Return SubtitleGenie's config directory, following each OS's convention."""
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "SubtitleGenie")
    if os.sys.platform == "darwin":  # macOS
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "SubtitleGenie")
    # Linux / other: respect XDG.
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "subtitlegenie")


def config_path() -> str:
    return os.path.join(config_dir(), "config.json")


# ---- schema ----------------------------------------------------------------

# Valid values for the movie-type decision.
MOVIE_TYPE_AUTO = "auto"   # detect from filename
MOVIE_TYPE_2D = "2d"
MOVIE_TYPE_3D = "3d"

ACTION_SIDECAR = "sidecar"
ACTION_EMBED = "embed"

MODE_ALWAYS = "always"
MODE_SMART = "smart"
MODE_NEVER = "never"

ASK = "ask"
NEVER = "never"


@dataclass
class Defaults:
    languages: list[str] = field(default_factory=lambda: ["en"])
    action: str = ACTION_SIDECAR          # sidecar | embed
    movie_type: str = MOVIE_TYPE_AUTO      # auto | 2d | 3d
    overwrite: bool = False                # replace subs that already exist
    hearing_impaired: str = "include"      # include | prefer | exclude
    forced: str = "include"                # include | prefer | exclude | only
    keep_original_on_embed: bool = False   # keep a copy of the pre-mux file
    # 3D subtitle rendering (see subgenie/threed.py).
    three_d_format: str = "auto"           # auto | hsbs | sbs | hou | ou
    three_d_disparity: int = 0             # per-eye horizontal shift (depth); 0 = screen plane
    three_d_keep_flat: bool = False        # also write the plain 2D .srt alongside the 3D .ass
    embed_tag: str = "SG"                   # marker on embedded track titles ("" = none)


@dataclass
class Prompts:
    # Per-decision ask policy: "ask" or "never".
    languages: str = ASK
    action: str = ASK
    movie_type: str = ASK
    overwrite: str = NEVER
    # Global override.
    mode: str = MODE_SMART   # always | smart | never


@dataclass
class Updates:
    check_on_run: bool = True        # look for a newer release when SubtitleGenie runs
    check_interval_hours: float = 0.0  # min hours between auto-checks; 0 = every run
    last_check: float = 0.0          # epoch seconds of the last automatic check


@dataclass
class OpenSubtitlesAuth:
    # API key is required by OpenSubtitles; username/password are optional and
    # only raise your download quota.
    username: str = ""
    password: str = ""


@dataclass
class Config:
    api_key: str = ""
    opensubtitles: OpenSubtitlesAuth = field(default_factory=OpenSubtitlesAuth)
    defaults: Defaults = field(default_factory=Defaults)
    prompts: Prompts = field(default_factory=Prompts)
    updates: Updates = field(default_factory=Updates)
    enable_fallbacks: bool = True   # use Podnapisi et al. when OpenSubtitles misses

    # -- ask logic ----------------------------------------------------------

    def should_ask(self, decision: str) -> bool:
        """Should SubtitleGenie prompt the user for ``decision`` this run?

        Resolves the global mode against the per-decision policy.
        """
        mode = self.prompts.mode
        if mode == MODE_NEVER:
            return False
        if mode == MODE_ALWAYS:
            return True
        # smart: defer to the decision's own policy.
        policy = getattr(self.prompts, decision, NEVER)
        return policy == ASK

    # -- (de)serialization --------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        cfg = cls()
        cfg.api_key = data.get("api_key", cfg.api_key)
        cfg.enable_fallbacks = data.get("enable_fallbacks", cfg.enable_fallbacks)

        auth = data.get("opensubtitles", {}) or {}
        cfg.opensubtitles = OpenSubtitlesAuth(
            username=auth.get("username", ""),
            password=auth.get("password", ""),
        )

        defaults = data.get("defaults", {}) or {}
        base = Defaults()
        cfg.defaults = Defaults(
            languages=list(defaults.get("languages", base.languages)),
            action=defaults.get("action", base.action),
            movie_type=defaults.get("movie_type", base.movie_type),
            overwrite=bool(defaults.get("overwrite", base.overwrite)),
            hearing_impaired=defaults.get("hearing_impaired", base.hearing_impaired),
            forced=defaults.get("forced", base.forced),
            keep_original_on_embed=bool(
                defaults.get("keep_original_on_embed", base.keep_original_on_embed)
            ),
            three_d_format=defaults.get("three_d_format", base.three_d_format),
            three_d_disparity=int(defaults.get("three_d_disparity", base.three_d_disparity)),
            three_d_keep_flat=bool(defaults.get("three_d_keep_flat", base.three_d_keep_flat)),
            embed_tag=defaults.get("embed_tag", base.embed_tag),
        )

        prompts = data.get("prompts", {}) or {}
        bp = Prompts()
        cfg.prompts = Prompts(
            languages=prompts.get("languages", bp.languages),
            action=prompts.get("action", bp.action),
            movie_type=prompts.get("movie_type", bp.movie_type),
            overwrite=prompts.get("overwrite", bp.overwrite),
            mode=prompts.get("mode", bp.mode),
        )

        updates = data.get("updates", {}) or {}
        bu = Updates()
        cfg.updates = Updates(
            check_on_run=bool(updates.get("check_on_run", bu.check_on_run)),
            check_interval_hours=float(
                updates.get("check_interval_hours", bu.check_interval_hours)
            ),
            last_check=float(updates.get("last_check", bu.last_check)),
        )
        return cfg


def load() -> Config:
    """Load config from disk, returning defaults if none exists or it's broken."""
    path = config_path()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return Config()
    if not isinstance(data, dict):
        return Config()
    return Config.from_dict(data)


def save(cfg: Config) -> str:
    """Write config to disk, creating the directory. Returns the path written."""
    os.makedirs(config_dir(), exist_ok=True)
    path = config_path()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(cfg.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path
