# Changelog

All notable changes to SubtitleGenie are recorded here. The release workflow
pulls the section matching each version tag into that release's notes, so this
file is the single source of truth for "what changed."

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- _Nothing yet — add lines here as you work; they move under a version heading
  when you cut a release._

## [0.1.0] - 2026-08-15

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

[Unreleased]: https://github.com/DeliciousMeatPop/SubGenie/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/DeliciousMeatPop/SubGenie/releases/tag/v0.1.0
