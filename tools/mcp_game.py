"""Snake Quest for pyxel-mcp: the `script` to give its tools (run, read_tilemap, read_audio, ...).

The server runs a script headlessly and drives the frames as fast as it can, but the game times everything by the
wall clock (`game.dt`): here every frame lasts 1/fps seconds, as in the tests and tools/balance.py, so a run of N
frames plays N/fps seconds whatever the machine. The profile is a fresh one in a temporary directory, so runs
neither read nor overwrite the player's. The App the server sees (`state` attrs, `until`) is the `Game`, e.g.
`stateID.name`, `level_counter`, `score`, `running_handler.map.snake.length`.

The server passes no arguments; the options of `snake-quest` (and --play) come from SNAKE_QUEST_ARGS, or write a
short script of your own that calls play():

    import sys; sys.path.insert(0, "/path/to/snake/tools")
    from mcp_game import play
    play(["--level", "hunted", "--difficulty", "hard", "--play"])
"""

import datetime
import os
import shlex
import tempfile

import pyxel

from snake_quest.cli import build_parser, settings_overrides
from snake_quest.game import Game


class SteppedGame(Game):
    """The game with a clock that advances one frame per update."""

    def update(self) -> None:
        self.dt = datetime.timedelta(seconds=1 / self.cfg.fps)
        self.handler.update()


def play(argv: list[str] | None = None) -> None:
    parser = build_parser()
    parser.add_argument("--play", action="store_true", help="start in the --level's mission screen, not the menu")
    args = parser.parse_args(argv)
    profile_dir = tempfile.mkdtemp(prefix="snake-quest-")
    pyxel.user_data_dir = lambda *names: profile_dir
    run = pyxel.run  # the server's, which observes the game inside this call

    def start(update, draw):
        if args.play:
            update.__self__.restart()
        run(update, draw)

    pyxel.run = start
    SteppedGame(overrides=settings_overrides(args), start_level=args.level)


if __name__ == "__main__":
    play(shlex.split(os.environ.get("SNAKE_QUEST_ARGS", "")))
