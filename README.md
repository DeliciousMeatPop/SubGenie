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
subtitlegenie movie.mkv --sync                # auto-align timing to the audio
subtitlegenie movie.mkv --sync-offset -2.5    # or shift timing by a fixed amount
subtitlegenie movie.mkv --overwrite           # replace existing subtitles
subtitlegenie movie.mkv -y                    # don't ask anything, use defaults
subtitlegenie movie.mkv --ask                 # ask about everything this run
```

### Fixing out-of-sync subtitles

Hash-matched OpenSubtitles results are already synced, but a fallback subtitle
can be off. Two options:

- `--sync` **auto-aligns** each subtitle to the movie's audio (fixes both a
  constant offset and framerate drift). It uses
  [ffsubsync](https://github.com/smacke/ffsubsync); install it once with
  `pip install ffsubsync`.
- `--sync-offset SECONDS` applies a **fixed shift** (e.g. `-2.5` to move subs
  2.5s earlier) — no extra tools needed.

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

## How 3D subtitles work

A plain `.srt` over a Side-by-Side or Over-Under 3D movie shows up **once**,
centered across the whole frame — straddling the seam between the two eye
images. On a 3D display each eye then only sees half the text, so it never
fuses. That's not a real 3D subtitle.

In **3D mode** SubtitleGenie rewrites the subtitle into a per-eye `.ass` file:

- **Side-by-Side (SBS/HSBS):** one copy centered in the left half, one in the
  right half. Half-SBS squeezes each eye horizontally, so the text is drawn at
  50% width to look right after the display stretches it back.
- **Over-Under (OU/HOU):** copies stacked in the top and bottom halves, with
  50% height for Half-OU.

On letterboxed (cinemascope) releases SubtitleGenie detects the active picture
area with ffmpeg (cropdetect) and places the subtitles just above the bottom of
the **visible image**, so they don't float in the middle or sit down in a black
bar. Without ffmpeg it falls back to near the bottom of the frame.

The layout is auto-detected from the filename (`HSBS`, `Half-OU`, …); override
with `--3d-format`. Depth defaults to the screen plane — nudge it with
`--3d-depth N` if you want the text to sit in front of or behind the screen.
Use `--keep-flat` to also keep the ordinary 2D subtitle beside the 3D one.

```bash
subtitlegenie "I Am Number Four 3D HSBS.mkv" --3d            # auto-detect layout
subtitlegenie movie.mkv --3d --3d-format hou --3d-depth 8    # force Over-Under, slight pop-out
```

> Frame resolution is read via ffprobe so the per-eye positions match your
> movie exactly; without ffprobe it assumes 1080p.

## How embedding works

With `--action embed` (or `defaults.action = embed`), SubtitleGenie muxes the
downloaded subtitles into the movie using ffmpeg — copying all existing streams
(no video/audio re-encode) and adding each subtitle as a soft track with correct
language metadata and forced disposition. The original is only replaced after a
successful mux; use `--keep-original` to leave a `.bak` copy behind.

Two things make the embedded tracks pleasant to live with:

- **They're tagged.** Each added track is titled like `English [SG]`, so in your
  player's track list you can tell SubtitleGenie's subtitles from the movie's own
  (`English [PGS]`, `Track 3`, …). Change or clear the marker with
  `config --set defaults.embed_tag SG`.
- **Your language auto-plays.** The track for your primary language (first in
  `defaults.languages`) is marked the *default*, and the movie's own default is
  cleared — so playback starts on your language even when you embedded `all`. If
  that language is already in the movie, its existing track becomes the default.

### Getting ffmpeg (only needed for embedding)

Sidecar mode needs nothing extra. Embedding needs ffmpeg, and if it isn't found
SubtitleGenie explains how to get it (with your OS's package-manager one-liner
and the official link, <https://ffmpeg.org/download.html>) and offers to fetch
it for you:

```bash
subtitlegenie install-ffmpeg
```

That downloads an official/trusted static build into SubtitleGenie's own folder
(`<config dir>/bin`) and uses it automatically — no PATH changes, and it's found
on PATH first if you already have it. We **don't** bundle ffmpeg in releases: the
useful builds are GPL and carry codec-patent baggage, so shipping them would drag
in license/patent obligations. Letting you pull an official build on demand keeps
that clean. On macOS the recommended route is `brew install ffmpeg`.

If ffmpeg still isn't present, SubtitleGenie safely falls back to sidecar files
so your download isn't wasted.

---

## Commands reference

```
subtitlegenie <paths...>        Find/place subtitles for file(s) or folder(s)
subtitlegenie setup             Interactive first-time configuration
subtitlegenie config --show     Print current settings and their location
subtitlegenie config --set K V  Set a config key (repeatable)
subtitlegenie languages         List every supported language and its codes
subtitlegenie update            Check for a newer version and offer to download it
subtitlegenie install-ffmpeg    Fetch ffmpeg into SubtitleGenie's folder (for embedding)
subtitlegenie --version
```

(`subgenie` works everywhere `subtitlegenie` does.)

### Staying up to date

On every run SubtitleGenie quietly checks GitHub for a newer release (the check
is silent when you're up to date). If there's one, it asks to update — and if you
say yes it does the whole thing for you:

1. downloads the build for your OS,
2. unzips the new executable **right next to your current one** (each version
   has its own name — `SubtitleGenie_win_v0.2.0.exe`, `..._mac_v0.2.0`,
   `..._linux_v0.2.0` — so nothing is overwritten), and
3. launches the new version with the **same movie you just dropped**, so the job
   simply continues on the new build. On Windows the new version opens in a fresh
   window; on macOS/Linux it takes over the same terminal.

You can also update on demand with `subtitlegenie update`. Skip the check for one
run with `--no-update-check`, throttle it to at most every N hours, or turn the
automatic check off entirely:

```bash
subtitlegenie config --set updates.check_interval_hours 24   # at most once a day
subtitlegenie config --set updates.check_on_run false        # off entirely
```

Old versions are left in place — delete them whenever you like.

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

---

![Visitors](https://api.visitorbadge.io/api/visitors?path=DeliciousMeatPop%2FSubGenie&label=People%20Who%20Forgot%20To%20Star%20This%20Repo&countColor=%23ba68c8&style=plastic)<br>
![Last Commit](https://img.shields.io/github/last-commit/DeliciousMeatPop/SubGenie?label=Last%20Updated)<br>
![Created](https://img.shields.io/github/created-at/DeliciousMeatPop/SubGenie?label=Created)<br>
![Monthly Commits](https://img.shields.io/github/commit-activity/m/DeliciousMeatPop/SubGenie?label=Monthly%20Commits)<br>

## ⭐ Do the thing

You’re already here. You’ve already scrolled.

Just hit the ⭐ and we both win.

⭐ Star this repo please

---

[![GitHub stars for this repo](https://img.shields.io/github/stars/DeliciousMeatPop/SubGenie?style=social)](https://github.com/DeliciousMeatPop/SubGenie) = **GitHub stars for this repo**

[![GitHub stars in total (all repos)](https://img.shields.io/github/stars/DeliciousMeatPop?style=social)](https://github.com/DeliciousMeatPop) = **GitHub stars in total (all repos)**

