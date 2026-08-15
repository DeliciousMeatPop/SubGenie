# SubtitleGenie 🧞

<p align="center">
  <img src="https://github.com/user-attachments/assets/f907702e-31cf-41b3-8983-d1dbe89b68f5" alt="Subtitle Genie" width="700">
</p>

**Drop a movie on it. It finds the subtitles, names them, or embeds them — done.**

SubtitleGenie is a small, cross-platform (Windows / macOS / Linux) tool that
takes a movie file, figures out what it is (title, year, **2D or 3D**), searches
for subtitles in **any language**, and then either:

- saves them as correctly-named **sidecar files** next to the movie
  (`Movie (2020).en.srt`, `Movie (2020).es.forced.srt` — the naming Plex and
  Jellyfin expect), **or**
- **embeds** them straight into the movie file (muxed with ffmpeg, no
  re-encoding).

Grab **all languages at once** or **pick and choose**. Configure it once and it
can run fully hands-off — literally drop a file and walk away — or ask you a few
questions each time. You decide, per decision.

> **Repo** is `subgenie`, the **app** is **SubtitleGenie**. The Python package
> and the short command alias are `subgenie`; the branded command and the
> downloadable app are `subtitlegenie`. They're the same thing.

---

## Features

- 🎯 **Frame-accurate matching** via OpenSubtitles file hashing — subtitles that
  actually line up, which matters especially for 3D releases whose runtime
  often differs from the 2D version.
- 🌍 **Any language** — pick a few, or `all`. Brazilian vs European Portuguese,
  Simplified vs Traditional Chinese, and the rest.
- 🎬 **3D aware** — auto-detects `3D`, `SBS`, `HSBS`, `HOU`, `Half-OU`, etc. from
  the filename, prefers matching 3D subtitles, and keeps the 3D tag in the
  sidecar name.
- 📁 **Sidecar or embed** — choose per run, or set a default.
- 🔁 **Fallback sources** — OpenSubtitles first (best), then keyless public
  sources (Podnapisi) when it comes up empty.
- ⚙️ **You control the questions** — every decision has a saved default and an
  "ask or just do it" policy. Go fully automatic or fully interactive.
- 📦 **Batch mode** — hand it a whole folder (optionally recursive).
- 🧠 **Skips what you already have** — won't re-download a language that's
  already present, unless you ask it to overwrite.

---

## Install

### Option A — download a prebuilt app (no Python needed)

Grab the archive for your OS from the
[**Releases**](https://github.com/DeliciousMeatPop/SubGenie/releases) page,
unzip it, and run the `subtitlegenie` executable inside. That's it — no Python,
no `pip`. (For **embedding** you still need [ffmpeg](https://ffmpeg.org/download.html)
on your `PATH`; sidecar mode needs nothing extra.)

### Option B — run from source

Needs **Python 3.8+**.

```bash
git clone https://github.com/DeliciousMeatPop/SubGenie.git
cd SubGenie
pip install -r requirements.txt
python run.py setup
```

### Option C — install the command

```bash
pip install .
subtitlegenie setup     # or the short alias: subgenie setup
```

---

## First-time setup

```bash
subtitlegenie setup      # or: python run.py setup
```

It walks you through:

1. **OpenSubtitles API key** — free, from
   <https://www.opensubtitles.com/en/consumers>. (Optional but strongly
   recommended; without it SubtitleGenie can only use keyless fallbacks.)
2. Optional OpenSubtitles **username/password** (raises your download quota).
3. Your **default languages**.
4. Default **action** (sidecar vs embed).
5. Default **movie type** (auto-detect / always 2D / always 3D).
6. **How often to ask** — smart / always / never.

Everything is saved to a plain JSON file you can hand-edit:

- Windows: `%APPDATA%\SubtitleGenie\config.json`
- macOS: `~/Library/Application Support/SubtitleGenie/config.json`
- Linux: `~/.config/subtitlegenie/config.json`

---

## Everyday use

### Just drop a movie on it

- **Windows** — drag a movie file (or several) onto `launchers/SubtitleGenie.bat`.
- **macOS** — `launchers/SubtitleGenie.command` (double-click, or run from Terminal).
- **Linux** — `launchers/subtitlegenie.sh /path/to/Movie.mkv`.

Or from a terminal, anywhere:

```bash
subtitlegenie "The Matrix (1999) 1080p BluRay.mkv"
subtitlegenie "/media/movies"                 # whole folder
subtitlegenie -r "/media/movies"              # folder, recursive
```

### Handy one-off flags

```bash
subtitlegenie movie.mkv --langs en,es,fr      # just these languages
subtitlegenie movie.mkv --langs all           # every language it knows
subtitlegenie movie.mkv --action embed        # mux into the file this time
subtitlegenie movie.mkv --3d                  # force 3D handling
subtitlegenie movie.mkv --2d                  # force plain 2D
subtitlegenie movie.mkv --overwrite           # replace existing subtitles
subtitlegenie movie.mkv -y                    # don't ask anything, use defaults
subtitlegenie movie.mkv --ask                 # ask about everything this run
```

---

## Controlling how much it asks

This is the heart of SubtitleGenie's config. There's a global **mode**:

| Mode     | Behavior                                                        |
|----------|----------------------------------------------------------------|
| `smart`  | Ask only about the decisions you flagged as "ask" (default).   |
| `always` | Ask about every decision, every run.                           |
| `never`  | Never ask — use your saved defaults. Drop-and-go.              |

...and, in `smart` mode, a per-decision **ask policy** (`ask` / `never`) for
`languages`, `action` (sidecar/embed), `movie_type` (2D/3D), and `overwrite`.

Set these in `setup`, or directly:

```bash
subtitlegenie config --show
subtitlegenie config --set prompts.mode never
subtitlegenie config --set defaults.languages en,es,pb
subtitlegenie config --set defaults.action embed
subtitlegenie config --set defaults.movie_type auto
subtitlegenie config --set prompts.action ask       # ask sidecar-vs-embed each time
subtitlegenie config --set prompts.languages never   # but never ask languages
```

**Example — total hands-off:** set `prompts.mode = never`,
`defaults.languages = en,es`, `defaults.action = sidecar`. Now every dropped
movie silently gets English + Spanish sidecars, correctly named, with no
prompts.

**Example — ask only the important thing:** `prompts.mode = smart`,
`prompts.action = ask`, everything else `never`. It uses your default languages
and auto-detects 2D/3D, but always asks whether to save-alongside or embed.

---

## How naming works (sidecar mode)

```
Movie (2020) 3D HSBS.mkv
Movie (2020) 3D HSBS.en.srt          ← English
Movie (2020) 3D HSBS.es.forced.srt   ← Spanish, forced/foreign-parts-only
Movie (2020) 3D HSBS.fr.sdh.srt      ← French, hearing-impaired (SDH)
```

Because subtitles are named from the movie's own filename, any `3D`/`HSBS`/etc.
tag is preserved automatically, and Plex/Jellyfin pick the tracks up with the
right language, forced, and SDH flags.

## How embedding works

With `--action embed` (or `defaults.action = embed`), SubtitleGenie muxes the
downloaded subtitles into the movie using ffmpeg — copying all existing streams
(no video/audio re-encode) and adding each subtitle as a soft track with correct
language metadata and forced disposition. The original is only replaced after a
successful mux; use `--keep-original` to leave a `.bak` copy behind.

If ffmpeg isn't installed, SubtitleGenie tells you and safely falls back to
sidecar files so your download isn't wasted.

---

## Commands reference

```
subtitlegenie <paths...>        Find/place subtitles for file(s) or folder(s)
subtitlegenie setup             Interactive first-time configuration
subtitlegenie config --show     Print current settings and their location
subtitlegenie config --set K V  Set a config key (repeatable)
subtitlegenie languages         List every supported language and its codes
subtitlegenie --version
```

(`subgenie` works everywhere `subtitlegenie` does.)

---

## Releases & versioning

Releases are built automatically by GitHub Actions. To cut one, push a version
tag:

```bash
git tag v0.2.0
git push origin v0.2.0
```

That builds standalone executables for Windows, macOS, and Linux, and opens a
**draft release** with those archives attached and release notes pre-filled from
[`CHANGELOG.md`](CHANGELOG.md). Review/edit the draft, then publish. See
[`docs/RELEASING.md`](docs/RELEASING.md) for the full flow and how the notes
template works.

---

## Development

```bash
pip install -r requirements.txt
pip install pytest
python -m pytest        # tests run offline, no network required
```

The codebase is deliberately small and dependency-light (only `requests` at
runtime; everything else is standard library). Providers are pluggable — see
`subgenie/providers/` to add another subtitle source.

---

## Notes & limitations

- OpenSubtitles enforces a daily download quota on the free tier; add a
  username/password in config for a higher one.
- Keyless fallback sources are best-effort and never hash-matched, so their
  sync isn't guaranteed — they're a safety net, not the primary path.
- SubtitleGenie downloads subtitles; please respect the terms of the sources
  you use.

## License

MIT — see the header in `pyproject.toml`.
