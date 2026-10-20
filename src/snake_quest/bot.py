"""Let a bot play levels, for balancing (tools/balance.py) and the winnability tests: a PathController heading for the
nearest apple, or with ammo for the nearest hostile entity, or without for a gun lying around (see `target`). `game`
is anything the running state can run on without a window (the tests' FakeGame, the tool's BotGame): it needs `cfg`,
`campaign`, `level_counter`, `score`, `dt`, `difficulty`, `profile`, `sm`, `change_state()` recording into
`requested_states`."""

from collections import Counter

import pyxel

from snake_quest.controls import PathController, nearest
from snake_quest.entity import ENTITY_NAMES, Apple, Critter, GoldenApple, GunPickup
from snake_quest.goals import CollectAllGoal
from snake_quest.states import StateID
from snake_quest.states.running import RunningStateHandler

# the levels the bot wins by eating apples. Not yummy: at 250 points (about 50 golden apples, ~1000 segments in the
# small room) the bot bites its tail at 70-200 points, while a person won it at the first try (playtest).
LEVELS = ("classic", "hunger", "hunted", "armed", "prey")

HUNT_LENGTH = 16  # segments: shorter, the bot eats before it hunts
food = nearest(Apple, GoldenApple, Critter)
guns = nearest(GunPickup)
foes = nearest(*(cls for cls in ENTITY_NAMES.values() if cls.hostile), clearance=0)


def target(snake, map):
    """What the level asks to collect first; then hunt with ammo (once long enough to afford a bite), fetch a gun
    without, eat otherwise."""
    wanted = [goal.entity_cls for goal in map.goals if isinstance(goal, CollectAllGoal)]
    if wanted and (goal := nearest(*wanted, clearance=0)(snake, map)):
        return goal
    if snake.weapon is not None and snake.weapon.ammo > 0 and len(snake) >= HUNT_LENGTH:
        return foes(snake, map) or food(snake, map)
    return guns(snake, map) or food(snake, map)


def play(game, level: str, seed: int, seconds: float) -> tuple[str, float]:
    """One run of `level`: ("won" | "wall" | "tail" | "killed" | "timeout", seconds played)."""
    pyxel.rseed(seed)
    game.level_counter = game.campaign.resolve(level)
    game.requested_states.clear()
    game.score = 0
    running = RunningStateHandler(game)
    running.snake.controller = PathController(target)
    for _ in range(int(seconds * game.cfg.fps)):
        running.update()
        if StateID.LEVEL_COMPLETE in game.requested_states:
            return "won", running.elapsed
        if StateID.DEATH in game.requested_states:
            if running.map.snake_killed:
                return "killed", running.elapsed  # starved, a hazard, a hunter
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
