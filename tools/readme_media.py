"""Render the README's gameplay montage and screenshots from the real game: headless, with the bot playing.

    python tools/readme_media.py docs/media                  # the montage and every screenshot
    python tools/readme_media.py docs/media --only montage --stills   # also a few frames of each segment as PNGs

The montage is a few seconds of play from levels across the arcs, cut together into one GIF, each with a caption
teasing what the level is about. A segment starts its level (no mission briefing), lets the bot play it unrecorded
for a while with a fixed seed, as `bot.play` does (in the Keeper's levels the pet steers itself and a HandBot is the
hand), then records. Unrecorded frames skip pyxel.flip, which waits for the frame time: only the game's look uses
`pyxel.frame_count`. The overview map comes from a profile with every arc open. Each frame lasts 1/fps seconds
whatever the machine (see mcp_game.py), so the same seed gives the same pictures; if a segment ends in a game over,
try another seed or fewer seconds.
"""

import argparse
import math
import tempfile
from pathlib import Path

import pyxel
from mcp_game import SteppedGame

from snake_quest.bot import take_over
from snake_quest.states.menu_common import COL_HIGHLIGHT, panel, text_width

SCALE = 2
CAPTION_MARGIN = 6  # px of panel around a caption, and below it to the footer

# level, seconds played before recording, seconds recorded, seed, caption
MONTAGE = [
    ("yummy", 40, 2.5, 1, "THE GARDEN: EAT AND GROW"),
    ("maneuver", 7.5, 2.5, 2, "PORTALS"),
    ("hunted", 18, 2.5, 1, "THE WILDS: BEETLES HUNT YOUR TAIL"),
    ("alpha", 9, 2.5, 2, "PICK UP A GUN: THE ALPHA AND ITS PACK"),
    ("turrets", 5.5, 2.5, 3, "THE FORTRESS: TURRETS SHOOT BACK"),
    ("ouroboros", 7, 2.5, 3, "OUROBOROS: A RIVAL SNAKE"),
    ("bats", 13, 2.5, 3, "THE CAVES: DARKNESS AND BATS"),
    ("asteroids", 8, 2.5, 1, "SPACE: ASTEROIDS BREAK UP"),
    ("crates", 20, 2.5, 1, "THE WORKSHOP: PUSH CRATES"),
    ("crow", 25.5, 2.5, 2, "THE KEEPER: YOU ARE THE HAND"),
]
BOSS_SHOT = ("crow", 25, 1)  # level, seconds the bot plays before the shot, seed


def step(game: SteppedGame, frames: int, caption: str | None = None) -> None:
    """Play `frames` frames; with a caption they are recorded (flipped) with the caption drawn over them."""
    for _ in range(frames):
        game.update()
        game.draw()
        if caption is not None:
            draw_caption(game, caption)
            pyxel.flip()


def draw_caption(game: SteppedGame, text: str) -> None:
    w, h = text_width(text) + 2 * CAPTION_MARGIN, pyxel.FONT_HEIGHT + CAPTION_MARGIN
    x = (game.cfg.width - w) // 2
    y = game.cfg.header.h + game.cfg.area.h - h - CAPTION_MARGIN
    panel(x, y, w, h)
    pyxel.text(x + CAPTION_MARGIN, y + CAPTION_MARGIN // 2 + 1, text, COL_HIGHLIGHT)


def start_level(game: SteppedGame, level: str, seed: int) -> None:
    """Start `level` without its mission briefing and let the bot play it."""
    pyxel.rseed(seed)
    game.start_level = game.campaign.resolve(level)
    game.restart()
    game.running_handler.intro_pending = False
    take_over(game.running_handler)


def shoot(game: SteppedGame, out: Path, name: str) -> None:
    pyxel.screenshot(str(out / f"{name}.png"), SCALE)
    print(f"{name}.png: {game.next_stateID.name}")


def montage(game: SteppedGame, out: Path, stills: bool) -> None:
    fps = game.cfg.fps
    pyxel.reset_screencast()
    for index, (level, warm_up, seconds, seed, caption) in enumerate(MONTAGE):
        start_level(game, level, seed)
        step(game, round(warm_up * fps))
        frames = round(seconds * fps)
        for part, count in enumerate((1, frames // 2 - 1, frames - frames // 2)):
            step(game, count, caption)
            if stills:
                pyxel.screenshot(str(out / f"montage-{index}-{part}.png"), 1)
        print(f"{level}: {game.next_stateID.name}")
    pyxel.screencast(str(out / "montage.gif"), SCALE)


def render(game: SteppedGame, out: Path, only: set[str], stills: bool) -> None:
    fps = game.cfg.fps
    for arc in game.campaign.arcs:  # every arc open, its fog lifted
        game.profile.complete_arc(arc.name)
    game.profile.see_arcs([arc.name for arc in game.campaign.arcs])
    if "map" in only:
        game.play()
        step(game, 4 * fps)
        shoot(game, out, "map")
    if "mission" in only:
        game.start_level = game.campaign.resolve("hunted")
        game.restart()
        step(game, fps)
        shoot(game, out, "mission")
    if "boss" in only:
        level, seconds, seed = BOSS_SHOT
        start_level(game, level, seed)
        step(game, seconds * fps)
        shoot(game, out, "boss")
    if "montage" in only:
        montage(game, out, stills)


def main() -> None:
    names = ["map", "mission", "boss", "montage"]
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=lambda value: Path(value).resolve(), help="directory for the images")
    parser.add_argument("--only", nargs="+", choices=names, default=names)
    parser.add_argument("--stills", action="store_true", help="also save three frames of each montage segment")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    profile_dir = tempfile.mkdtemp(prefix="snake-quest-")
    pyxel.user_data_dir = lambda *names: profile_dir
    recorded = math.ceil(sum(seconds for _, _, seconds, _, _ in MONTAGE)) + 1
    init = pyxel.init
    pyxel.init = lambda *a, **kw: init(*a, **kw, headless=True, capture_sec=recorded)
    mouse = pyxel.mouse
    pyxel.mouse = lambda visible: mouse(False)  # Pyxel draws the cursor into the screen image
    pyxel.run = lambda update, draw: render(update.__self__, args.out, set(args.only), args.stills)
    SteppedGame(overrides={"music": False, "effects": False})


if __name__ == "__main__":
    main()
