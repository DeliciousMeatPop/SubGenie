"""Command-line entry point.

Two shapes of invocation:
  * ``subgenie <movie-or-folder> [more...]`` - the main job. Drag a file onto a
    launcher and this is what runs.
  * ``subgenie config ...`` / ``subgenie setup`` / ``subgenie languages`` -
    manage settings.

The CLI's job is to turn config + flags + (optional) prompts into a concrete
``RunOptions`` and hand off to ``core``. Whether any given decision is asked or
taken from the saved default is governed entirely by ``Config.should_ask``.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from . import __version__, config as config_module, ui
from .config import (
    ACTION_EMBED, ACTION_SIDECAR, ASK, NEVER,
    MODE_ALWAYS, MODE_NEVER, MODE_SMART,
    MOVIE_TYPE_2D, MOVIE_TYPE_3D, MOVIE_TYPE_AUTO,
    Config,
)
from .core import RunOptions, process_movie
from .embed import ffmpeg_available
from .languages import Language, resolve_many
from .mediainfo import MovieInfo, is_video_file, parse
from .providers import OpenSubtitlesProvider, PodnapisiProvider
from .providers.base import Provider


# --------------------------------------------------------------------------
# argument parsing
# --------------------------------------------------------------------------

KNOWN_COMMANDS = {"setup", "config", "languages"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="subtitlegenie",
        description="Drop a movie on it; it finds, names, and/or embeds subtitles.",
        epilog="Commands: setup | config [--show] [--set KEY VALUE] | languages",
    )
    parser.add_argument("--version", action="version", version=f"SubtitleGenie {__version__}")

    # main run arguments (the default when the first arg is a path)
    parser.add_argument("paths", nargs="*", help="Movie file(s) or folder(s).")
    parser.add_argument("-l", "--langs", help="Comma-separated languages (codes/names) or 'all'.")
    parser.add_argument("--action", choices=[ACTION_SIDECAR, ACTION_EMBED],
                        help="Save sidecar files or embed into the movie.")
    parser.add_argument("--3d", dest="three_d", action="store_true",
                        help="Treat input as a 3D release.")
    parser.add_argument("--2d", dest="two_d", action="store_true",
                        help="Treat input as a plain 2D release.")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace subtitles that already exist.")
    parser.add_argument("--keep-original", action="store_true",
                        help="When embedding, keep a .bak copy of the original file.")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="Don't ask anything; use saved defaults (like mode=never).")
    parser.add_argument("--ask", action="store_true",
                        help="Ask about every decision this run (like mode=always).")
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Recurse into subfolders when given a directory.")
    return parser


# --------------------------------------------------------------------------
# provider assembly
# --------------------------------------------------------------------------

def build_providers(cfg: Config) -> list[Provider]:
    providers: list[Provider] = []
    opensubs = OpenSubtitlesProvider(
        api_key=cfg.api_key,
        username=cfg.opensubtitles.username,
        password=cfg.opensubtitles.password,
    )
    if opensubs.is_available():
        providers.append(opensubs)
    if cfg.enable_fallbacks:
        providers.append(PodnapisiProvider())
    return providers


# --------------------------------------------------------------------------
# input expansion
# --------------------------------------------------------------------------

def collect_movies(paths: list[str], recursive: bool) -> list[str]:
    """Expand file/folder args into a de-duplicated list of movie files."""
    movies: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        real = os.path.abspath(path)
        if real not in seen and is_video_file(real):
            seen.add(real)
            movies.append(real)

    for path in paths:
        if os.path.isdir(path):
            if recursive:
                for root, _, files in os.walk(path):
                    for name in files:
                        add(os.path.join(root, name))
            else:
                for name in os.listdir(path):
                    add(os.path.join(path, name))
        elif os.path.isfile(path):
            add(path)
        else:
            print(ui.yellow(f"Skipping (not found): {path}"))
    return sorted(movies)


# --------------------------------------------------------------------------
# decision resolution (config + flags + prompts -> RunOptions)
# --------------------------------------------------------------------------

def _resolve_mode(cfg: Config, args) -> None:
    """Apply -y/--ask overrides onto the config's global ask mode in-place."""
    if args.yes:
        cfg.prompts.mode = MODE_NEVER
    elif args.ask:
        cfg.prompts.mode = MODE_ALWAYS


def resolve_languages(cfg: Config, args) -> list[Language]:
    if args.langs:
        found, unknown = resolve_many(args.langs.split(","))
        if unknown:
            print(ui.yellow("Unknown languages ignored: ") + ", ".join(unknown))
        if found:
            return found
    default, _ = resolve_many(cfg.defaults.languages)
    if not default:
        default, _ = resolve_many(["en"])
    if cfg.should_ask("languages"):
        return ui.select_languages(default)
    return default


def resolve_action(cfg: Config, args) -> str:
    if args.action:
        return args.action
    if cfg.should_ask("action"):
        default_idx = 0 if cfg.defaults.action == ACTION_SIDECAR else 1
        note = "" if ffmpeg_available() else ui.dim("  (ffmpeg not found – embed will fall back to sidecars)")
        choice = ui.choose(
            "\nWhat should I do with the subtitles?" + ("\n" + note if note else ""),
            [
                (ACTION_SIDECAR, "Save as sidecar files next to the movie (rename)"),
                (ACTION_EMBED, "Embed them into the movie file (mux with ffmpeg)"),
            ],
            default_index=default_idx,
        )
        return choice
    return cfg.defaults.action


def resolve_3d(cfg: Config, args, info: MovieInfo) -> bool:
    if args.three_d:
        return True
    if args.two_d:
        return False

    setting = cfg.defaults.movie_type
    if setting == MOVIE_TYPE_3D:
        base = True
    elif setting == MOVIE_TYPE_2D:
        base = False
    else:  # auto
        base = info.is_3d

    # Only ask when the policy says to. On 'auto' we trust detection silently
    # unless the global mode forces asking.
    if cfg.should_ask("movie_type"):
        detected = "3D" if info.is_3d else "2D"
        label = f" (detected: {detected}{' / ' + info.three_d_format if info.three_d_format else ''})"
        choice = ui.choose(
            f"\nIs '{info.filename}' 2D or 3D?{label}",
            [(MOVIE_TYPE_2D, "Plain 2D"), (MOVIE_TYPE_3D, "3D")],
            default_index=1 if base else 0,
        )
        return choice == MOVIE_TYPE_3D
    return base


def resolve_overwrite(cfg: Config, args) -> bool:
    if args.overwrite:
        return True
    if cfg.should_ask("overwrite"):
        return ui.confirm("Replace subtitles that already exist?", default=cfg.defaults.overwrite)
    return cfg.defaults.overwrite


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def _print_result(result) -> None:
    info = result.info
    header = f"{info.title}" + (f" ({info.year})" if info.year else "")
    print("\n" + ui.bold(header) + ui.dim(f"  [{os.path.basename(info.path)}]"))
    if result.error:
        print(ui.red(f"  ! {result.error}"))
    for outcome in result.outcomes:
        lang = outcome.language.name
        if outcome.status == "downloaded":
            print(ui.green(f"  + {lang}: ") + f"saved {os.path.basename(outcome.path or '')}")
        elif outcome.status == "embedded":
            print(ui.green(f"  + {lang}: ") + "embedded into movie")
        elif outcome.status == "skipped":
            print(ui.dim(f"  = {lang}: {outcome.detail}"))
        elif outcome.status == "notfound":
            print(ui.yellow(f"  - {lang}: not found"))
        else:
            print(ui.red(f"  ! {lang}: {outcome.detail}"))


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------

def cmd_languages() -> int:
    from .languages import all_languages
    print(ui.bold("Supported languages") + ui.dim("  (sidecar code / 3-letter / name)"))
    for lang in all_languages():
        print(f"  {lang.sidecar_code:<4} {lang.alpha3:<5} {lang.name}")
    print(ui.dim("\nUse any of these with --langs, or 'all' for everything."))
    return 0


def cmd_config_show(cfg: Config) -> int:
    import json
    print(ui.bold("Config file: ") + config_module.config_path())
    printable = cfg.to_dict()
    # Mask the API key / password so a shared terminal doesn't leak them.
    if printable.get("api_key"):
        printable["api_key"] = "***set***"
    if printable.get("opensubtitles", {}).get("password"):
        printable["opensubtitles"]["password"] = "***set***"
    print(json.dumps(printable, indent=2, sort_keys=True))
    return 0


def cmd_config_set(cfg: Config, pairs) -> int:
    for key, value in pairs:
        if not _apply_dotted(cfg, key, value):
            print(ui.red(f"Unknown or invalid config key: {key}"))
            return 2
    path = config_module.save(cfg)
    print(ui.green(f"Saved {len(pairs)} change(s) to ") + path)
    return 0


def _apply_dotted(cfg: Config, key: str, value: str) -> bool:
    """Set a dotted config key from a string value. Returns success."""
    parts = key.split(".")
    coerced = _coerce(value)

    try:
        if parts == ["api_key"]:
            cfg.api_key = value
        elif parts == ["enable_fallbacks"]:
            cfg.enable_fallbacks = _as_bool(value)
        elif parts[:1] == ["opensubtitles"] and len(parts) == 2:
            setattr(cfg.opensubtitles, parts[1], value)
        elif parts[:1] == ["defaults"] and len(parts) == 2:
            field = parts[1]
            if field == "languages":
                cfg.defaults.languages = [v.strip() for v in value.split(",") if v.strip()]
            elif field in ("overwrite", "keep_original_on_embed"):
                setattr(cfg.defaults, field, _as_bool(value))
            elif hasattr(cfg.defaults, field):
                setattr(cfg.defaults, field, value)
            else:
                return False
        elif parts[:1] == ["prompts"] and len(parts) == 2:
            if hasattr(cfg.prompts, parts[1]):
                setattr(cfg.prompts, parts[1], value)
            else:
                return False
        else:
            return False
    except (AttributeError, ValueError):
        return False
    return True


def _coerce(value: str):
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    return value


def _as_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def cmd_setup(cfg: Config) -> int:
    print(ui.banner())
    print(ui.bold("\nSetup") + ui.dim("  – press Enter to keep the current value."))

    current = "set" if cfg.api_key else "not set"
    print(ui.dim(f"\nOpenSubtitles API key ({current}). Get a free one at "
                 "https://www.opensubtitles.com/en/consumers"))
    key = input("API key: ").strip()
    if key:
        cfg.api_key = key

    if ui.confirm("\nAdd an OpenSubtitles username/password for a higher download quota?",
                  default=False):
        cfg.opensubtitles.username = input("  Username: ").strip() or cfg.opensubtitles.username
        cfg.opensubtitles.password = input("  Password: ").strip() or cfg.opensubtitles.password

    # Default languages.
    default_codes = ", ".join(cfg.defaults.languages)
    raw = input(f"\nDefault languages [{default_codes}]: ").strip()
    if raw:
        found, unknown = resolve_many([t for c in raw.split(",") for t in c.split()])
        if unknown:
            print(ui.yellow("  Ignored unknown: ") + ", ".join(unknown))
        if found:
            cfg.defaults.languages = [l.sidecar_code for l in found]

    # Default action.
    cfg.defaults.action = ui.choose(
        "\nDefault action:",
        [(ACTION_SIDECAR, "Save sidecar files (rename)"),
         (ACTION_EMBED, "Embed into the movie")],
        default_index=0 if cfg.defaults.action == ACTION_SIDECAR else 1,
    )

    # Movie type default.
    mt_idx = {MOVIE_TYPE_AUTO: 0, MOVIE_TYPE_2D: 1, MOVIE_TYPE_3D: 2}.get(cfg.defaults.movie_type, 0)
    cfg.defaults.movie_type = ui.choose(
        "\nMovie type default:",
        [(MOVIE_TYPE_AUTO, "Auto-detect from filename"),
         (MOVIE_TYPE_2D, "Always 2D"),
         (MOVIE_TYPE_3D, "Always 3D")],
        default_index=mt_idx,
    )

    # How often to ask.
    mode_idx = {MODE_SMART: 0, MODE_ALWAYS: 1, MODE_NEVER: 2}.get(cfg.prompts.mode, 0)
    cfg.prompts.mode = ui.choose(
        "\nHow much should I ask when you run it?",
        [(MODE_SMART, "Smart – only ask about things you told me to ask about"),
         (MODE_ALWAYS, "Always – ask about every decision"),
         (MODE_NEVER, "Never – just use my defaults (drop and go)")],
        default_index=mode_idx,
    )

    if cfg.prompts.mode == MODE_SMART:
        print(ui.dim("\nFor 'smart' mode, choose which decisions to ask about:"))
        cfg.prompts.languages = ASK if ui.confirm("  Ask which languages each time?",
                                                  default=cfg.prompts.languages == ASK) else NEVER
        cfg.prompts.action = ASK if ui.confirm("  Ask sidecar-vs-embed each time?",
                                               default=cfg.prompts.action == ASK) else NEVER
        cfg.prompts.movie_type = ASK if ui.confirm("  Ask 2D-vs-3D each time?",
                                                   default=cfg.prompts.movie_type == ASK) else NEVER

    path = config_module.save(cfg)
    print(ui.green("\nSaved config to ") + path)
    if not cfg.api_key:
        print(ui.yellow("Note: without an API key, SubtitleGenie can only use keyless fallbacks."))
    return 0


# --------------------------------------------------------------------------
# main run
# --------------------------------------------------------------------------

def run_jobs(cfg: Config, args) -> int:
    movies = collect_movies(args.paths, args.recursive)
    if not movies:
        print(ui.yellow("No movie files found in the given path(s)."))
        return 1

    providers = build_providers(cfg)
    if not providers:
        print(ui.red("No subtitle providers available."))
        print(ui.dim("Run 'subgenie setup' to add an OpenSubtitles API key, "
                     "or enable fallbacks in config."))
        return 1

    print(ui.banner())
    print(ui.dim(f"Found {len(movies)} movie file(s). "
                 f"Providers: {', '.join(p.name for p in providers)}."))

    # Resolve the decisions that are the same for every movie once up front.
    languages = resolve_languages(cfg, args)
    action = resolve_action(cfg, args)
    overwrite = resolve_overwrite(cfg, args)

    if action == ACTION_EMBED and not ffmpeg_available():
        print(ui.yellow("ffmpeg not found – subtitles will be saved as sidecar files instead."))

    exit_code = 0
    for movie_path in movies:
        info = parse(movie_path)
        treat_as_3d = resolve_3d(cfg, args, info)
        options = RunOptions(
            languages=languages,
            action=action,
            treat_as_3d=treat_as_3d,
            overwrite=overwrite,
            keep_original_on_embed=args.keep_original or cfg.defaults.keep_original_on_embed,
            hearing_impaired=cfg.defaults.hearing_impaired,
            forced=cfg.defaults.forced,
        )
        result = process_movie(info, options, providers, log=lambda m: print(ui.dim(m)))
        _print_result(result)
        if result.error:
            exit_code = 2

    if ui.is_interactive():
        # When launched by a double-click / drag-drop the window would vanish;
        # pause so the user can read the summary.
        try:
            input(ui.dim("\nDone. Press Enter to close."))
        except (EOFError, KeyboardInterrupt):
            pass
    return exit_code


def _dispatch_command(command: str, rest: list[str], cfg: Config) -> int:
    """Handle the non-run subcommands (setup / config / languages)."""
    if command == "setup":
        return cmd_setup(cfg)
    if command == "languages":
        return cmd_languages()
    if command == "config":
        cfg_parser = argparse.ArgumentParser(prog="subgenie config")
        cfg_parser.add_argument("--show", action="store_true",
                                help="Print current config and its location.")
        cfg_parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), action="append",
                                help="Set a dotted key, e.g. --set defaults.action embed.")
        cfg_args = cfg_parser.parse_args(rest)
        if cfg_args.set:
            return cmd_config_set(cfg, cfg_args.set)
        return cmd_config_show(cfg)
    return 1  # unreachable


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cfg = config_module.load()

    # Dispatch subcommands by first token so drag-dropped paths (which come
    # first) never collide with argparse subparser handling.
    if argv and argv[0] in KNOWN_COMMANDS:
        return _dispatch_command(argv[0], argv[1:], cfg)

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.paths:
        parser.print_help()
        print(ui.dim("\nTip: run 'subgenie setup' first, then drop a movie file onto it."))
        return 0

    _resolve_mode(cfg, args)

    # First run with no API key and no config file: guide the user.
    if not cfg.api_key and not os.path.exists(config_module.config_path()):
        print(ui.yellow("No config found. Let's set up quickly first.\n"))
        if ui.is_interactive():
            cmd_setup(cfg)
            cfg = config_module.load()
            _resolve_mode(cfg, args)

    try:
        return run_jobs(cfg, args)
    except KeyboardInterrupt:
        print(ui.dim("\nInterrupted."))
        return 130


if __name__ == "__main__":
    sys.exit(main())
