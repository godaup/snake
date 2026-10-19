"""Command line entry point (`snake-quest` / `python -m snake_quest`)."""

import argparse
from pathlib import Path

from snake_quest import __version__, difficulty
from snake_quest.campaign import load_campaign


def level_number(value: str) -> int:
    """argparse type: a level given by campaign number or name."""
    campaign = load_campaign()
    try:
        return campaign.resolve(value)
    except (IndexError, KeyError) as e:
        names = ", ".join(f"{level.number}={level.name}" for level in campaign.levels)
        raise argparse.ArgumentTypeError(f"{e.args[0]} (choose from {names})") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="snake-quest", description="A level-based snake game built with Pyxel.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--level", type=level_number, default=1, help="level to start (and restart) at, by number or name"
    )
    parser.add_argument("--scale", type=int, help="window scale factor (default from settings.yaml)")
    parser.add_argument("--mute", action="store_true", help="disable music and sound effects")
    parser.add_argument(
        "--difficulty", choices=difficulty.NAMES, help="play at this difficulty (not saved; default: the menu's)"
    )
    parser.add_argument(
        "--debug", action="store_true", help="draw collision points, the hidden path and what is under the mouse"
    )
    parser.add_argument(
        "--preview",
        metavar="PNG",
        type=lambda value: Path(value).resolve(),  # before pyxel.init() changes the working directory
        help="render the --level to an image instead of playing",
    )
    return parser


def settings_overrides(args: argparse.Namespace) -> dict:
    """Translate parsed arguments into overrides for settings.yaml."""
    overrides = {}
    if args.scale is not None:
        overrides["scale"] = args.scale
    if args.mute:
        overrides["music"] = False
        overrides["effects"] = False
    if args.difficulty:
        overrides["start_difficulty"] = args.difficulty
    if args.debug:
        overrides["debug"] = True
    return overrides


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.preview:
        preview(load_campaign().level(args.level), args.preview)
        return
    # imported late so that --help and --version work without initializing pyxel
    from snake_quest.game import Game

    Game(overrides=settings_overrides(args), start_level=args.level)


def preview(level, filename: Path) -> None:
    import pyxel

    from snake_quest.campaign import load_campaign
    from snake_quest.preview import render

    pyxel.init(16, 16, headless=True)
    load_campaign().load_sprites()
    render(level, filename)
    print(f"{level.number} {level.name}: {filename}")
