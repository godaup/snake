"""Every level must be winnable (see ROADMAP.md): a bot plays it through. Rebalancing a level? Run these."""

import pytest
import pyxel

from snake_quest.campaign import load_campaign
from snake_quest.controls import PathController, nearest
from snake_quest.entity import Apple, GoldenApple
from snake_quest.states import StateID
from snake_quest.states.running import RunningStateHandler

CAMPAIGN = load_campaign()
SEEDS = (5, 2, 3)  # the first win counts: the bot is good, but not perfect
# levels the bot can win by eating apples, with the play time it may take (s)
LEVELS = {"classic": 90, "yummy": 60, "hunger": 150}


@pytest.mark.parametrize(("name", "seconds"), LEVELS.items())
def test_level_is_winnable(assets, game, name, seconds):
    """A bot that heads for the nearest apple along the shortest way beats the level."""
    game.level_counter = CAMPAIGN.resolve(name)
    results = []
    for seed in SEEDS:
        pyxel.rseed(seed)
        game.requested_states.clear()
        game.score = 0
        running = RunningStateHandler(game)
        running.snake.controller = PathController(nearest(Apple, GoldenApple))
        for _ in range(24 * seconds):
            running.update()
            if StateID.DEATH in game.requested_states or StateID.LEVEL_COMPLETE in game.requested_states:
                break
        if StateID.LEVEL_COMPLETE in game.requested_states:
            return
        results.append((seed, game.requested_states[-1], len(running.snake), round(running.elapsed)))
    pytest.fail(f"the bot never won {name}: {results}")
