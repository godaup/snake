"""Render the README's screenshots and gameplay clip from the real game: headless, with the bot playing.

    python tools/readme_media.py docs/media                  # every shot and the clip
    python tools/readme_media.py docs/media --only menu hunger

A level shot starts the level (no mission briefing), lets the bot play it for a while with a fixed seed, as
`bot.play` does (in the Keeper's levels the pet steers itself and a HandBot is the hand), and saves the screen. The
menu and the overview map come from a profile with every arc open. Each frame lasts 1/fps seconds whatever the
machine (see mcp_game.py), so the same seed gives the same pictures; if a shot shows a game over, try another seed.
"""

import argparse
import tempfile
from pathlib import Path

import pyxel
from mcp_game import SteppedGame

from snake_quest.bot import take_over

SCALE = 2
CLIP_SECONDS = 9

# name: (level, seconds the bot plays before the shot, seed)
LEVEL_SHOTS = {
    "maneuver": ("maneuver", 25, 3),
    "hunger": ("hunger", 30, 1),
    "alpha": ("alpha", 30, 2),
    "fortress": ("turrets", 25, 1),
    "ouroboros": ("ouroboros", 25, 1),
    "caves": ("bats", 25, 1),
    "space": ("gravity", 25, 1),
    "workshop": ("crates", 20, 1),
    "keeper": ("crow", 25, 1),
}
CLIP = ("crow", 12, 1)  # level, seconds played before the recording starts, seed


def step(game: SteppedGame, frames: int) -> None:
    for _ in range(frames):
        game.update()
        game.draw()
        pyxel.flip()


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


def render(game: SteppedGame, out: Path, only: set[str]) -> None:
    fps = game.cfg.fps
    for arc in game.campaign.arcs:  # every arc open, its fog lifted
        game.profile.complete_arc(arc.name)
    game.profile.see_arcs([arc.name for arc in game.campaign.arcs])
    if "menu" in only:
        step(game, 3 * fps)
        shoot(game, out, "menu")
    if "map" in only:
        game.play()
        step(game, 4 * fps)
        shoot(game, out, "map")
    if "mission" in only:
        game.start_level = game.campaign.resolve("hunted")
        game.restart()
        step(game, fps)
        shoot(game, out, "mission")
    for name, (level, seconds, seed) in LEVEL_SHOTS.items():
        if name in only:
            start_level(game, level, seed)
            step(game, seconds * fps)
            shoot(game, out, name)
    if "clip" in only:
        level, seconds, seed = CLIP
        start_level(game, level, seed)
        step(game, seconds * fps)
        pyxel.reset_screencast()
        step(game, CLIP_SECONDS * fps)
        pyxel.screencast(str(out / "clip.gif"), SCALE)
        print(f"clip.gif: {game.next_stateID.name}")


def main() -> None:
    names = ["menu", "map", "mission", *LEVEL_SHOTS, "clip"]
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("out", type=lambda value: Path(value).resolve(), help="directory for the images")
    parser.add_argument("--only", nargs="+", choices=names, default=names)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    profile_dir = tempfile.mkdtemp(prefix="snake-quest-")
    pyxel.user_data_dir = lambda *names: profile_dir
    init = pyxel.init
    pyxel.init = lambda *a, **kw: init(*a, **kw, headless=True, capture_sec=CLIP_SECONDS + 1)
    mouse = pyxel.mouse
    pyxel.mouse = lambda visible: mouse(False)  # Pyxel draws the cursor into the screen image
    pyxel.run = lambda update, draw: render(update.__self__, args.out, set(args.only))
    SteppedGame(overrides={"music": False, "effects": False})


if __name__ == "__main__":
    main()
