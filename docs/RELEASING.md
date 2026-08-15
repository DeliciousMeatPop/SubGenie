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

## Your edits are safe: an existing release is never overwritten

Once a release for a tag exists, the workflow **skips build and release
entirely** and leaves it untouched (you'll see a "Release exists" notice in the
Actions run). This matters because of a GitHub subtlety: publishing a *draft*
whose tag didn't exist yet makes GitHub **create the tag**, which re-triggers
this workflow — and without the guard that second run would overwrite your
published release with freshly-generated notes, wiping any edits.

**To regenerate a release** (e.g. its notes came out wrong), delete the existing
release first, then push the tag / re-run the workflow:

```bash
gh release delete v0.2.0 --yes        # delete the release (keeps or removes the tag)
git push --delete origin v0.2.0       # only if you also want to move the tag
git tag -f v0.2.0 && git push -f origin v0.2.0
```

Until you delete it, re-runs are no-ops — safe by design.

## How the release notes are built

`scripts/build_release_notes.py` assembles the body:

- **The changelog sits near the top of every release.** The script reads
  `CHANGELOG.md` and drops the relevant section wherever the template has
  `{{CHANGELOG}}`, so the "what changed" list is always current and lives high
  up — you never hand-copy it. It looks for the section in this order:
  1. an explicit `## [X.Y.Z]` heading for the version being released, else
  2. the `## [Unreleased]` section — so notes you keep under *Unreleased* still
     show up **without** having to move them under a version heading at tag time,
  3. and only if both are empty does a "fill me in" placeholder appear.

  Moving Unreleased → `## [X.Y.Z] - <date>` before tagging is still the tidy
  habit (it keeps the file's history straight), but it's no longer required for
  the notes to be correct.
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
