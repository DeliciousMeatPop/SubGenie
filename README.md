# SubtitleGenie 🧞

**Drop a movie on it. It finds the subtitles, names them, or embeds them — done.**

SubGenie is a small, cross-platform (Windows / macOS / Linux) command-line tool
that takes a movie file, figures out what it is (title, year, **2D or 3D**),
searches for subtitles in **any language**, and then either:

- saves them as correctly-named **sidecar files** next to the movie
  (`Movie (2020).en.srt`, `Movie (2020).es.forced.srt` — the naming Plex and
  Jellyfin expect), **or**
- **embeds** them straight into the movie file (muxed with ffmpeg, no
  re-encoding).

Grab **all languages at once** or **pick and choose**. Configure it once and it
can run fully hands-off — literally drop a file and walk away — or ask you a few
questions each time. You decide, per decision.

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

You need **Python 3.8+**. That's it for sidecar mode. For **embedding**, also
install [ffmpeg](https://ffmpeg.org/download.html) and make sure it's on your
`PATH`.

### Option A — run from source (no install)

```bash
git clone https://github.com/DeliciousMeatPop/SubGenie.git
cd SubGenie
pip install -r requirements.txt
python run.py setup
```

### Option B — install the command

```bash
pip install .
subgenie setup
```

This gives you a `subgenie` command anywhere.

---

## First-time setup

```bash
python run.py setup      # or: subgenie setup
```

It walks you through:

1. **OpenSubtitles API key** — free, from
   <https://www.opensubtitles.com/en/consumers>. (Optional but strongly
   recommended; without it SubGenie can only use keyless fallbacks.)
2. Optional OpenSubtitles **username/password** (raises your download quota).
3. Your **default languages**.
4. Default **action** (sidecar vs embed).
5. Default **movie type** (auto-detect / always 2D / always 3D).
6. **How often to ask** — smart / always / never.

Everything is saved to a plain JSON file you can hand-edit:

- Windows: `%APPDATA%\SubGenie\config.json`
- macOS: `~/Library/Application Support/SubGenie/config.json`
- Linux: `~/.config/subgenie/config.json`

---

## Everyday use

### Just drop a movie on it

- **Windows** — drag a movie file (or several) onto `launchers/SubGenie.bat`.
- **macOS** — `launchers/SubGenie.command` (double-click, or run from Terminal).
- **Linux** — `launchers/subgenie.sh /path/to/Movie.mkv`.

Or from a terminal, anywhere:

```bash
subgenie "The Matrix (1999) 1080p BluRay.mkv"
subgenie "/media/movies"                 # whole folder
subgenie -r "/media/movies"              # folder, recursive
```

### Handy one-off flags

```bash
subgenie movie.mkv --langs en,es,fr      # just these languages
subgenie movie.mkv --langs all           # every language SubGenie knows
subgenie movie.mkv --action embed        # mux into the file this time
subgenie movie.mkv --3d                  # force 3D handling
subgenie movie.mkv --2d                  # force plain 2D
subgenie movie.mkv --overwrite           # replace existing subtitles
subgenie movie.mkv -y                    # don't ask anything, use defaults
subgenie movie.mkv --ask                 # ask about everything this run
```

---

## Controlling how much it asks

This is the heart of SubGenie's config. There's a global **mode**:

| Mode     | Behavior                                                        |
|----------|----------------------------------------------------------------|
| `smart`  | Ask only about the decisions you flagged as "ask" (default).   |
| `always` | Ask about every decision, every run.                           |
| `never`  | Never ask — use your saved defaults. Drop-and-go.              |

...and, in `smart` mode, a per-decision **ask policy** (`ask` / `never`) for
`languages`, `action` (sidecar/embed), `movie_type` (2D/3D), and `overwrite`.

Set these in `setup`, or directly:

```bash
subgenie config --show
subgenie config --set prompts.mode never
subgenie config --set defaults.languages en,es,pb
subgenie config --set defaults.action embed
subgenie config --set defaults.movie_type auto
subgenie config --set prompts.action ask       # ask sidecar-vs-embed each time
subgenie config --set prompts.languages never   # but never ask languages
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

With `--action embed` (or `defaults.action = embed`), SubGenie muxes the
downloaded subtitles into the movie using ffmpeg — copying all existing streams
(no video/audio re-encode) and adding each subtitle as a soft track with correct
language metadata and forced disposition. The original is only replaced after a
successful mux; use `--keep-original` to leave a `.bak` copy behind.

If ffmpeg isn't installed, SubGenie tells you and safely falls back to sidecar
files so your download isn't wasted.

---

## Commands reference

```
subgenie <paths...>        Find/place subtitles for file(s) or folder(s)
subgenie setup             Interactive first-time configuration
subgenie config --show     Print current settings and their location
subgenie config --set K V  Set a config key (repeatable)
subgenie languages         List every supported language and its codes
subgenie --version
```

---

## Development

```bash
pip install -r requirements.txt
pip install pytest
python -m pytest        # 42 tests, no network required
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
- SubGenie downloads subtitles; please respect the terms of the sources you use.

## License

MIT — see the header in `pyproject.toml`.
