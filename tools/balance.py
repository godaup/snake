"""Measure level balance: a bot (PathController, heading for the nearest apple) plays each level at each difficulty
with several seeds, and the win rate, the median time to win and what killed it are printed.

    python tools/balance.py                                  # every level the bot can play, every difficulty
    python tools/balance.py --levels hunger --difficulties medium hard --seeds 12
    python tools/balance.py --levels hedges --no-hand    # the Keeper's levels with nobody keeping the garden

The bot knows where every apple is, so a person needs longer; use this to compare levels and difficulties, and
playtesting to set medium. tests/test_winnable.py checks the bands (see WIN_RATES there; `pytest -m slow`).
"""

import argparse
import datetime
import statistics
import sys
from pathlib import Path

import omegaconf
import pyxel

from snake_quest import difficulty
from snake_quest.bot import LEVELS, win_rate
from snake_quest.campaign import load_campaign
from snake_quest.profile import Profile
from snake_quest.states import StateID

SETTINGS = Path(__file__).resolve().parent.parent / "src/snake_quest/settings.yaml"


class BotGame:
    """Just enough of Game for a level to run without a window (like the tests' FakeGame)."""

    def __init__(self, campaign, name: str, settings: Path = SETTINGS):
        self.cfg = omegaconf.OmegaConf.load(settings)
        self.campaign = campaign
        self.level_counter = 1
        self.score = 0
        self.dt = datetime.timedelta(seconds=1 / self.cfg.fps)
        self.profile = Profile(difficulty=name)
        self.requested_states: list[StateID] = []
        self.sm = type("Silent", (), {"effect": lambda self, name: None})()
        self.backdrop = None

    @property
    def difficulty(self) -> difficulty.Difficulty:
        return difficulty.load(self.cfg, self.profile.difficulty)

    def change_state(self, state: StateID) -> None:
        self.requested_states.append(state)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--levels", nargs="+", default=LEVELS)
    parser.add_argument("--difficulties", nargs="+", default=difficulty.NAMES, choices=difficulty.NAMES)
    parser.add_argument("--seeds", type=int, default=8)
    parser.add_argument("--seconds", type=float, default=240, help="give up a run after this much play time")
    parser.add_argument("--no-hand", action="store_true", help="the Keeper's levels without the hand bot")
    args = parser.parse_args()
    pyxel.init(16, 16, headless=True)
    campaign = load_campaign()
    campaign.load_sprites()
    print(f"{'level':<10} {'difficulty':<10} {'wins':>6}  {'median':>7}  outcomes")
    for level in args.levels:
        for name in args.difficulties:
            rate, wins, outcomes = win_rate(
                BotGame(campaign, name), level, range(args.seeds), args.seconds, hand=not args.no_hand
            )
            median = f"{statistics.median(wins):.0f}s" if wins else "-"
            rest = ", ".join(f"{key} {count}" for key, count in outcomes.most_common() if key != "won")
            print(f"{level:<10} {name:<10} {rate:>6.0%}  {median:>7}  {rest}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
