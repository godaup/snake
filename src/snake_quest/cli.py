"""Command line entry point (`snake-quest` / `python -m snake_quest`)."""

import argparse
from pathlib import Path

from snake_quest import __version__

LEVELS_DIR = Path(__file__).parent / "levels"


def available_levels() -> list[int]:
    return sorted(int(p.stem) for p in LEVELS_DIR.glob("*.yaml") if p.stem.isdigit())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="snake-quest", description="A level-based snake game built with Pyxel.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--level", type=int, default=1, choices=available_levels(), help="level to start (and restart) at"
    )
    parser.add_argument("--scale", type=int, help="window scale factor (default from settings.yaml)")
    parser.add_argument("--mute", action="store_true", help="disable music and sound effects")
    parser.add_argument("--debug", action="store_true", help="draw collision points")
    return parser


def settings_overrides(args: argparse.Namespace) -> dict:
    """Translate parsed arguments into overrides for settings.yaml."""
    overrides = {}
    if args.scale is not None:
        overrides["scale"] = args.scale
    if args.mute:
        overrides["music"] = False
        overrides["effects"] = False
    if args.debug:
        overrides["debug"] = True
    return overrides


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    # imported late so that --help and --version work without initializing pyxel
    from snake_quest.game import Game

    Game(overrides=settings_overrides(args), start_level=args.level)
