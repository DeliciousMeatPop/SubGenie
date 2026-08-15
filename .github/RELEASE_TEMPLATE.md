## SubtitleGenie 🧞 {{VERSION}}

<p align="center">
  <img src="https://github.com/user-attachments/assets/f907702e-31cf-41b3-8983-d1dbe89b68f5" alt="Subtitle Genie" width="700">
</p>

<!--
  Default release-notes template. The workflow substitutes three placeholders
  (each written as a double-brace token): VERSION -> e.g. 0.2.0, TAG -> e.g.
  v0.2.0, and CHANGELOG -> the matching section from CHANGELOG.md.
  For fully custom notes on a specific release, add a file named for its tag
  under .github/release-notes/ and it is used instead of this template.
-->

### 📝 What changed in {{VERSION}}

{{CHANGELOG}}

---

### ⬇️ Download & run

Grab the archive for your OS from the **Assets** section below, unpack it, and
run the `subtitlegenie` executable inside. **No Python required.**

| OS | Archive |
|----|---------|
| 🪟 Windows | `SubtitleGenie_Win_{{VERSION}}.zip` |
| 🍎 MacOS | `SubtitleGenie_Mac_{{VERSION}}.tar.gz` |
| 🐧 Linux | `SubtitleGenie_Linux_{{VERSION}}.tar.gz` |

First run: `subtitlegenie setup` to add your free OpenSubtitles API key and
pick your defaults. Then just drop a movie on it. `subgenie setup` also works!

> For **embedding** subtitles into movies you also need
> [ffmpeg](https://ffmpeg.org/download.html) on your `PATH`. Saving subtitles as
> sidecar files needs nothing extra.

### 🔗 Links

- 📖 [README](https://github.com/DeliciousMeatPop/SubGenie/blob/main/README.md)
- 📋 [Full changelog](https://github.com/DeliciousMeatPop/SubGenie/blob/main/CHANGELOG.md)
