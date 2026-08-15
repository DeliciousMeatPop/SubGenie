"""SubtitleGenie - drop a movie on it and it finds, names, and/or embeds subtitles.

A cross-platform (Windows / macOS / Linux) command-line tool that:
  * identifies a movie file (title, year, 2D/3D) from its name and content hash,
  * searches OpenSubtitles (with public fallbacks) for subtitles in any language,
  * downloads the best match for the languages you want, and
  * either saves them as correctly-named sidecar files (Plex/Jellyfin style)
    or muxes them straight into the movie file.

Everything is driven by a config file so you can pick, per decision, whether
SubtitleGenie asks you or just uses your saved default.
"""

__version__ = "0.1.0"
__app_name__ = "SubtitleGenie"
__user_agent__ = f"{__app_name__} v{__version__}"

__all__ = ["__version__", "__app_name__", "__user_agent__"]
