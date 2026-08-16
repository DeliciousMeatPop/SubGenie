# Changelog

All notable changes to SubtitleGenie are recorded here. The release workflow
pulls the section matching each version tag into that release's notes, so this
file is the single source of truth for "what changed."

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

_Nothing yet — new entries go here and are moved under a version heading automatically at release time._

## [0.0.5] - 2026-08-16

### Fixed
- **Embedding into a movie that already has subtitle tracks no longer fails.**
  BluRay rips usually carry bitmap (PGS) subtitle tracks; the old mux forced
  every subtitle stream to a text codec, so ffmpeg tried to transcode those
  bitmaps to text and aborted the whole embed ("Subtitle encoding currently only
  possible from text to text or bitmap to bitmap"). Existing streams are now
  copied untouched, and the codec/language/forced metadata are applied only to
  the subtitle streams we add — at the correct offset, so their language tags no
  longer land on the movie's own tracks.
- **Each release's notes now list only that release's changes.** The workflow
  auto-promotes `## [Unreleased]` into a dated `## [X.Y.Z]` section at release
  time and commits it back, so `[Unreleased]` is cleared every release instead
  of accumulating. You just keep adding notes under `[Unreleased]`; no manual
  moving needed.

## [0.0.4] - 2026-08-15

### Added
- **ffmpeg help & opt-in install.** When embedding is requested but ffmpeg isn't
  found, SubtitleGenie now prints the official download link
  (<https://ffmpeg.org/download.html>), per-OS PATH instructions, and package-
  manager one-liners — and offers to fetch it for you. `subtitlegenie
  install-ffmpeg` downloads an official/trusted static build (gyan.dev on
  Windows, John Van Sickle on Linux) into `<config dir>/bin` and uses it
  automatically; ffmpeg on PATH still takes priority. macOS is guided to
  `brew install ffmpeg`. We don't bundle ffmpeg in releases (GPL + codec-patent
  reasons); the on-demand download keeps that clean.

### Fixed
- Removed the leftover "this is a draft" footer from generated release notes, so
  it no longer has to be deleted by hand on every release.

## [0.0.3] - 2026-08-15

### Added
- **Self-update that installs itself.** On a normal run (or via
  `subtitlegenie update`) SubtitleGenie checks GitHub for a newer release
  (interactive, throttled to once a day). If you accept, it downloads the archive
  for your OS, unzips the new executable **next to your current one** (version-
  stamped names never collide), and hands off to it — on Windows it opens the new
  version in a fresh console, on macOS/Linux it replaces the running process in
  the same terminal — carrying along the same movie you dropped, so the update is
  a single click and the job continues on the new version. Suppress a single run
  with `--no-update-check`; turn the automatic check off with
  `config --set updates.check_on_run false`.
- Release archives now contain a clearly named binary,
  `SubtitleGenie_<os>_v<version>` (`win`/`mac`/`linux`, e.g.
  `SubtitleGenie_win_v0.0.3.exe`), and the build stamps that version into the
  binary so `--version` and the update check report the release it was built
  from.

### Fixed
- The Windows release build failed at the version-stamp step: an inline
  `python -c "…"` ran under PowerShell, which parsed the regex `[^"]` as an array
  index. Version stamping now lives in `scripts/stamp_version.py`, so it works on
  every runner.

## [0.0.2] - 2026-08-15

### Added
- **Real 3D subtitles.** In 3D mode SubtitleGenie now rewrites the downloaded
  subtitle into a per-eye `.ass` file: for Side-by-Side it draws one copy in the
  left half and one in the right (each horizontally squeezed for Half-SBS), and
  for Over-Under it stacks top/bottom copies (vertically squeezed for Half-OU).
  Previously the 3D option only affected naming/matching, so a flat subtitle was
  rendered once across the seam and didn't fuse on a 3D display.
  - New flags: `--3d-format {auto,hsbs,sbs,hou,ou}`, `--3d-depth N`
    (per-eye shift; 0 = screen plane), `--keep-flat` (also keep the plain 2D
    subtitle). New config keys: `defaults.three_d_format`,
    `defaults.three_d_disparity`, `defaults.three_d_keep_flat`.
  - Frame resolution is probed with ffprobe so the per-eye positions match the
    actual movie; falls back to 1080p when ffprobe isn't available.
  - Embedding 3D subtitles into MKV keeps them as ASS (positioning preserved);
    MP4 can't carry positioned subtitles, so use MKV or sidecar mode for 3D.

### Fixed
- Release notes now fall back to the **Unreleased** changelog section when a tag
  has no matching `## [X.Y.Z]` heading, so notes kept under Unreleased show up in
  the draft instead of a "no entry" placeholder.
- The release workflow no longer overwrites an existing release. Publishing a
  draft re-creates its tag and re-triggers the workflow; it now detects the
  existing release and skips, preserving any manual edits. Delete the release to
  regenerate it.

## [0.0.1] - 2026-08-15

First public build. 🎉

### Added
- Drop-a-movie workflow: identify a movie (title, year, 2D/3D) from its
  filename and OpenSubtitles content hash, then find subtitles for it.
- Subtitles in any language — one, several, or `all`; Brazilian vs European
  Portuguese and Simplified vs Traditional Chinese kept distinct.
- **3D awareness**: auto-detects `3D`/`SBS`/`HSBS`/`HOU`/`Half-OU` tags, prefers
  matching 3D subtitles, and preserves the tag in sidecar filenames.
- Two output modes: correctly-named **sidecar** files (Plex/Jellyfin
  convention, with `forced`/`sdh` flags) or **embedding** into the movie via
  ffmpeg (lossless container remux, correct language metadata + forced
  disposition).
- Config-driven "ask or just do it": every decision (languages, action,
  2D/3D, overwrite) has a saved default plus an ask policy, with a global
  `smart` / `always` / `never` mode for fully hands-off runs.
- Skips languages that already exist (sidecar or embedded) unless `--overwrite`.
- Pluggable providers: OpenSubtitles primary (hash-matched), Podnapisi keyless
  fallback.
- Cross-platform drag-drop launchers for Windows, macOS, and Linux.
- `setup`, `config`, and `languages` subcommands.

[Unreleased]: https://github.com/DeliciousMeatPop/SubGenie/compare/v0.0.5...HEAD
[0.0.5]: https://github.com/DeliciousMeatPop/SubGenie/releases/tag/v0.0.5
[0.0.4]: https://github.com/DeliciousMeatPop/SubGenie/releases/tag/v0.0.4
[0.0.3]: https://github.com/DeliciousMeatPop/SubGenie/releases/tag/v0.0.3
[0.0.2]: https://github.com/DeliciousMeatPop/SubGenie/releases/tag/v0.0.2
[0.0.1]: https://github.com/DeliciousMeatPop/SubGenie/releases/tag/v0.0.1
