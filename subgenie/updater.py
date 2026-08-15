"""Check GitHub Releases for a newer SubtitleGenie and offer to fetch it.

This is intentionally conservative: any network hiccup degrades to "no update
info" rather than interrupting a run, and the automatic check is throttled to at
most once a day (tracked in config) so normal use never hammers the API.

We never try to replace a running executable in place - that's fragile and
platform-specific. Instead we download the release archive for the current OS
and tell the user where it is, so they can unzip and swap it in themselves.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import __user_agent__, __version__

try:
    import requests
except ImportError:  # pragma: no cover - requests is a declared dependency
    requests = None  # type: ignore

# The GitHub repo that publishes releases. Kept here (not user-config) because
# it's an identity, not a preference.
REPO = "DeliciousMeatPop/SubGenie"
_API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
_TIMEOUT = 8


@dataclass
class Asset:
    name: str
    url: str
    size: int = 0


@dataclass
class Release:
    tag: str
    version: str
    url: str
    assets: list[Asset] = field(default_factory=list)


def parse_version(text: str) -> tuple[int, ...]:
    """Turn 'v1.2.3', '1.2', '2.0.0-rc1' into a comparable tuple of ints.

    Stops at the first non-numeric component so pre-release suffixes don't break
    comparison (they simply don't raise the number).
    """
    text = (text or "").strip().lstrip("vV")
    nums: list[int] = []
    for part in re.split(r"[.\-+_]", text):
        match = re.match(r"\d+", part)
        if not match:
            break
        nums.append(int(match.group()))
    return tuple(nums) or (0,)


def is_newer(candidate: str, current: str) -> bool:
    """True if ``candidate`` is a strictly higher version than ``current``."""
    return parse_version(candidate) > parse_version(current)


def platform_key() -> str:
    """One of 'windows' / 'macos' / 'linux' for the running OS."""
    if os.name == "nt" or sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def pick_asset(assets: list[Asset], platform: Optional[str] = None) -> Optional[Asset]:
    """Pick the release archive that matches this OS (by name substring)."""
    key = platform or platform_key()
    for asset in assets:
        if key in asset.name.lower():
            return asset
    return None


def fetch_latest(timeout: int = _TIMEOUT) -> Optional[Release]:
    """Return the latest published release, or ``None`` on any problem."""
    if not requests:
        return None
    headers = {
        "User-Agent": __user_agent__,
        "Accept": "application/vnd.github+json",
    }
    try:
        response = requests.get(_API_LATEST, headers=headers, timeout=timeout)
    except requests.RequestException:
        return None
    if not response.ok:
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    tag = data.get("tag_name") or ""
    if not tag:
        return None
    assets = [
        Asset(a.get("name", ""), a.get("browser_download_url", ""), int(a.get("size") or 0))
        for a in (data.get("assets") or [])
        if a.get("browser_download_url")
    ]
    return Release(tag=tag, version=tag.lstrip("vV"), url=data.get("html_url", ""), assets=assets)


def check_for_update(current: str = __version__) -> Optional[Release]:
    """Return the latest release only if it's newer than ``current``; else None."""
    release = fetch_latest()
    if release and is_newer(release.version, current):
        return release
    return None


ProgressFn = Callable[[int, int], None]


def download_asset(
    asset: Asset,
    dest_dir: str,
    *,
    timeout: int = 60,
    progress: Optional[ProgressFn] = None,
) -> str:
    """Stream a release asset to ``dest_dir``. Returns the written file path."""
    if not requests:
        raise RuntimeError("The 'requests' package is required to download updates.")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, asset.name or "SubtitleGenie-update")
    headers = {"User-Agent": __user_agent__}
    with requests.get(asset.url, headers=headers, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or asset.size or 0)
        done = 0
        with open(dest, "wb") as handle:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                handle.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    return dest
