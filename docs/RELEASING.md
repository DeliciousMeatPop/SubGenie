# Releasing SubtitleGenie

Releases are automated. You provide a **version**; GitHub Actions builds the
apps for every OS and opens a **draft** release for you to review and publish.

## TL;DR

1. Move your new entries in `CHANGELOG.md` from `## [Unreleased]` into a new
   `## [X.Y.Z] - YYYY-MM-DD` section.
2. Bump `version` in `pyproject.toml` and `subgenie/__init__.py` to `X.Y.Z`.
3. Commit that.
4. Tag and push:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
5. Watch the **Actions** tab. When it finishes, go to **Releases**, open the
   new **draft**, give the notes a final read, and click **Publish**.

> Prefer buttons? In the **Actions** tab pick **Build & draft release** →
> **Run workflow**, type `vX.Y.Z`, and run it. Same result, no local tag needed.

## What the workflow does

`.github/workflows/release.yml`:

1. **version** — figures out the tag/version from the pushed tag or the input.
2. **build** (Windows, macOS, Linux in parallel) — installs the package,
   bundles it into a single standalone `subtitlegenie` executable with
   PyInstaller, and packs it (with the README and changelog) into
   `SubtitleGenie-<version>-<os>.{zip,tar.gz}`.
3. **release** — collects those archives and opens a **draft** release whose
   notes come from your templates (below). It never publishes on its own.

## How the release notes are built

`scripts/build_release_notes.py` assembles the body:

- **The changelog sits near the top of every release.** The script reads
  `CHANGELOG.md`, grabs the section whose heading matches the version being
  released, and drops it in wherever the template has `{{CHANGELOG}}`. So the
  "what changed" list is always current and lives high up in the notes — you
  never hand-copy it.
- **Default template:** `.github/RELEASE_TEMPLATE.md`. This is the layout used
  for every release. Edit it to change the standard structure (downloads table,
  links, footer, etc.). Placeholders it can use: `{{VERSION}}`, `{{TAG}}`,
  `{{CHANGELOG}}`.
- **Per-release override (the "special" ones):** if a file
  `.github/release-notes/<tag>.md` exists (e.g. `v0.1.0.md`), it is used
  *instead of* the default template for that release — while still getting the
  same placeholder substitution, so it too can embed `{{CHANGELOG}}`. This is
  how the very first release gets its fuller, one-off write-up. For ordinary
  releases you don't create one of these, and the default template is used.

### Preview notes locally

```bash
python scripts/build_release_notes.py v0.2.0
```

Prints exactly what the draft's body will be, so you can sanity-check the
changelog extraction before tagging.

## Adding a special write-up for a future release

Only when you want a release to read differently from the standard template
(a milestone, a big rewrite), create `.github/release-notes/vX.Y.Z.md`, keep a
`{{CHANGELOG}}` placeholder somewhere near the top, and write whatever extra
prose you like around it.
