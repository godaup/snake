"""Every level must be winnable (see ROADMAP.md): a bot plays it through (snake_quest.bot). Rebalancing a level or a
difficulty? Measure with tools/balance.py and run `pytest -m slow` for the bands."""

import pytest

from snake_quest import difficulty
from snake_quest.bot import LEVELS, play, win_rate

SEEDS = (5, 2, 3)  # the first win counts: the bot is good, but not perfect
BAND_SEEDS = range(8)
# win rate of the bot per difficulty (over BAND_SEEDS): easier must be easier, and even nightmare must be winnable
# (the ceilings only guard against a difficulty being nearly as easy as medium; the bot plays Classic's open room
# well, so its nightmare ceiling is generous)
WIN_RATES = {"easy": (0.75, 1.0), "medium": (0.5, 1.0), "hard": (0.25, 0.9), "nightmare": (0.1, 0.7)}
SECONDS = 240  # play time after which a run counts as lost


@pytest.mark.parametrize("name", LEVELS)
def test_level_is_winnable(assets, game, name):
    """A bot that heads for the nearest apple along the shortest way beats the level at medium."""
    results = []
    for seed in SEEDS:
        outcome, elapsed = play(game, name, seed, SECONDS)
        if outcome == "won":
            return
        results.append((seed, outcome, round(elapsed)))
    pytest.fail(f"the bot never won {name}: {results}")


@pytest.mark.slow
@pytest.mark.parametrize("name", LEVELS)
def test_difficulties_keep_their_win_rates(assets, game, name):
    """Each difficulty lands in its band of bot win rates, and no harder difficulty is won (clearly) more often."""
    rates = {}
    for level in difficulty.NAMES:
        game.profile.difficulty = level
        rates[level], _, _ = win_rate(game, name, BAND_SEEDS, SECONDS)
    for level, (low, high) in WIN_RATES.items():
        assert low <= rates[level] <= high, (name, rates)
    # harder is never won more often, give or take one unlucky run of the bot
    ordered = [rates[level] for level in difficulty.NAMES]
    slack = 1 / len(BAND_SEEDS)
    assert all(harder <= easier + slack for easier, harder in zip(ordered, ordered[1:], strict=False)), (name, rates)
