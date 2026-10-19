"""Let a bot play levels, for balancing (tools/balance.py) and the winnability tests: a PathController heading for the
nearest apple. `game` is anything the running state can run on without a window (the tests' FakeGame, the tool's
BotGame): it needs `cfg`, `campaign`, `level_counter`, `score`, `dt`, `difficulty`, `profile`, `sm`, `change_state()`
recording into `requested_states`."""

from collections import Counter

import pyxel

from snake_quest.controls import PathController, nearest
from snake_quest.entity import Apple, GoldenApple
from snake_quest.states import StateID
from snake_quest.states.running import RunningStateHandler

# the levels the bot wins by eating apples. Not yummy: at 250 points (about 50 golden apples, ~1000 segments in the
# small room) the bot bites its tail at 12-100 points; the goal is set for people, to be confirmed by playtesting.
LEVELS = ("classic", "hunger")


def play(game, level: str, seed: int, seconds: float) -> tuple[str, float]:
    """One run of `level`: ('won' | 'wall' | 'tail' | 'starved' | 'timeout', seconds played)."""
    pyxel.rseed(seed)
    game.level_counter = game.campaign.resolve(level)
    game.requested_states.clear()
    game.score = 0
    running = RunningStateHandler(game)
    running.snake.controller = PathController(nearest(Apple, GoldenApple))
    for _ in range(int(seconds * game.cfg.fps)):
        running.update()
        if StateID.LEVEL_COMPLETE in game.requested_states:
            return "won", running.elapsed
        if StateID.DEATH in game.requested_states:
            if running.map.snake_killed:
                return "starved", running.elapsed
            return ("tail" if running.snake.self_intersect() else "wall"), running.elapsed
    return "timeout", running.elapsed


def win_rate(game, level: str, seeds, seconds: float) -> tuple[float, list[float], Counter]:
    """Fraction of runs won, the play times of the wins and the outcomes of all runs."""
    outcomes, wins = Counter(), []
    for seed in seeds:
        outcome, elapsed = play(game, level, seed, seconds)
        outcomes[outcome] += 1
        if outcome == "won":
            wins.append(elapsed)
    return len(wins) / len(seeds), wins, outcomes
