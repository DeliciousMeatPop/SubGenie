"""Finding, explaining, and (optionally) installing ffmpeg.

SubtitleGenie needs ffmpeg for two things: embedding subtitles into a movie, and
reading a movie's resolution (ffprobe) for 3D positioning. It calls them as
separate programs, so nothing here links ffmpeg into our code.

We deliberately do **not** ship ffmpeg inside our releases: useful ffmpeg builds
are GPL and carry codec-patent baggage, so redistributing them would drag in
license/patent obligations. Instead we (a) explain how to install it, and
(b) offer an *opt-in* download where the user pulls an official/trusted build
that we drop into SubtitleGenie's own folder and use automatically - the user
distributes it to themselves, which keeps us clear of redistribution.
"""

from __future__ import annotations

import os
import platform
import shutil
from typing import Optional

from . import config

# The canonical place to send people. FFmpeg.org doesn't host binaries itself
# (patent reasons) but links to the trusted builders from here.
OFFICIAL_DOWNLOAD_URL = "https://ffmpeg.org/download.html"

# Trusted, widely-used static builds linked from the official download page.
_WIN_BUILD = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
_LINUX_BUILD_AMD64 = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
_LINUX_BUILD_ARM64 = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz"


def local_bin_dir() -> str:
    """Where an opt-in install drops ffmpeg/ffprobe (inside our config dir)."""
    return os.path.join(config.config_dir(), "bin")


def _exe(name: str) -> str:
    return name + (".exe" if os.name == "nt" else "")


def find(name: str) -> Optional[str]:
    """Locate ``ffmpeg``/``ffprobe``: PATH first, then our local install dir."""
    on_path = shutil.which(name)
    if on_path:
        return on_path
    candidate = os.path.join(local_bin_dir(), _exe(name))
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return None


def ffmpeg_path() -> Optional[str]:
    return find("ffmpeg")


def ffprobe_path() -> Optional[str]:
    return find("ffprobe")


def available() -> bool:
    return ffmpeg_path() is not None


# ---- guidance -------------------------------------------------------------

def guidance() -> str:
    """A per-OS, copy-pasteable explanation of how to install ffmpeg."""
    lines = [
        "ffmpeg is needed to embed subtitles (and to read 3D frame sizes).",
        f"Official downloads & builds: {OFFICIAL_DOWNLOAD_URL}",
        "",
    ]
    if os.name == "nt":
        lines += [
            "Windows — easiest options:",
            "  • winget:  winget install Gyan.FFmpeg",
            "  • choco:   choco install ffmpeg",
            "  Or download the 'release essentials' zip, unzip it, and add the",
            "  extracted 'bin' folder to your PATH:",
            "    Settings → System → About → Advanced system settings →",
            "    Environment Variables → Path → Edit → New → paste the bin path.",
        ]
    elif platform.system() == "Darwin":
        lines += [
            "macOS — easiest option:",
            "  • Homebrew:  brew install ffmpeg   (handles PATH for you)",
            "  Or download a build from the link above and put ffmpeg/ffprobe on",
            "  your PATH (e.g. copy them into /usr/local/bin).",
        ]
    else:
        lines += [
            "Linux — use your package manager:",
            "  • Debian/Ubuntu:  sudo apt install ffmpeg",
            "  • Fedora:         sudo dnf install ffmpeg",
            "  • Arch:           sudo pacman -S ffmpeg",
            "  These put ffmpeg on your PATH automatically.",
        ]
    lines += [
        "",
        "Or let SubtitleGenie fetch a build into its own folder for you:",
        "    subtitlegenie install-ffmpeg",
    ]
    return "\n".join(lines)


def can_auto_install() -> bool:
    """Whether the opt-in downloader supports this OS."""
    if os.name == "nt":
        return True
    if platform.system() == "Linux":
        return True
    return False  # macOS: Homebrew is the reliable path; we guide instead.


# ---- opt-in install -------------------------------------------------------

class InstallError(Exception):
    """Raised when the assisted ffmpeg download/extraction can't complete."""


def _build_url() -> Optional[str]:
    if os.name == "nt":
        return _WIN_BUILD
    if platform.system() == "Linux":
        machine = platform.machine().lower()
        if machine in ("aarch64", "arm64"):
            return _LINUX_BUILD_ARM64
        return _LINUX_BUILD_AMD64
    return None


def _wanted_basenames() -> set[str]:
    return {_exe("ffmpeg"), _exe("ffprobe")}


def _members_to_extract(names: list[str]) -> dict[str, str]:
    """Map wanted basename -> archive member path, for ffmpeg/ffprobe only."""
    wanted = _wanted_basenames()
    out: dict[str, str] = {}
    for member in names:
        base = os.path.basename(member)
        if base in wanted and base not in out:
            out[base] = member
    return out


def install(progress=None) -> list[str]:
    """Download a trusted static ffmpeg build into ``local_bin_dir``.

    Returns the list of installed executable paths. Raises InstallError on any
    problem (including "not supported on this OS"). The caller is expected to
    treat this as opt-in - it only runs when the user asks.
    """
    try:
        import requests  # local import: only needed for this path
    except ImportError as exc:  # pragma: no cover
        raise InstallError("The 'requests' package is required to download ffmpeg.") from exc

    url = _build_url()
    if url is None:
        raise InstallError(
            "Automatic install isn't available on this OS. "
            "On macOS use 'brew install ffmpeg'."
        )

    dest_dir = local_bin_dir()
    os.makedirs(dest_dir, exist_ok=True)

    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="subtitlegenie_ffmpeg_")
    archive_path = os.path.join(tmpdir, os.path.basename(url.split("?")[0]))
    try:
        _download(url, archive_path, progress)
        installed = _extract(archive_path, dest_dir)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if not installed:
        raise InstallError("Downloaded archive did not contain ffmpeg/ffprobe.")
    return installed


def _download(url: str, dest: str, progress) -> None:
    import requests
    from . import __user_agent__
    headers = {"User-Agent": __user_agent__}
    try:
        with requests.get(url, headers=headers, stream=True, timeout=120) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with open(dest, "wb") as handle:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except requests.RequestException as exc:
        raise InstallError(f"Download failed: {exc}") from exc


def _extract(archive_path: str, dest_dir: str) -> list[str]:
    os.makedirs(dest_dir, exist_ok=True)
    lower = archive_path.lower()
    installed: list[str] = []

    if lower.endswith(".zip"):
        import zipfile
        with zipfile.ZipFile(archive_path) as archive:
            members = _members_to_extract(archive.namelist())
            for base, member in members.items():
                out = os.path.join(dest_dir, base)
                with archive.open(member) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                installed.append(out)
    elif lower.endswith((".tar.xz", ".txz", ".tar.gz", ".tgz")):
        import tarfile
        mode = "r:xz" if ".xz" in lower or lower.endswith(".txz") else "r:gz"
        with tarfile.open(archive_path, mode) as archive:
            members = _members_to_extract(archive.getnames())
            for base, member in members.items():
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                out = os.path.join(dest_dir, base)
                with extracted as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                installed.append(out)
    else:
        raise InstallError(f"Unrecognized archive type: {os.path.basename(archive_path)}")

    if os.name != "nt":
        for path in installed:
            os.chmod(path, 0o755)
    return installed
