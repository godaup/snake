"""Let a bot play levels, for balancing (tools/balance.py) and the winnability tests: a PathController heading for the
nearest apple, or with ammo for the nearest hostile entity, or without for a gun lying around (see `target`). `game`
is anything the running state can run on without a window (the tests' FakeGame, the tool's BotGame): it needs `cfg`,
`campaign`, `level_counter`, `score`, `dt`, `difficulty`, `profile`, `sm`, `change_state()` recording into
`requested_states`."""

from collections import Counter

import pyxel

from snake_quest.controls import PathController, nearest
from snake_quest.entity import ENTITY_NAMES, Apple, Critter, GoldenApple, Turret, WeaponPickup
from snake_quest.goals import CollectAllGoal, DestroyAllGoal, ExitGoal
from snake_quest.states import StateID
from snake_quest.states.running import RunningStateHandler

# the levels the bot wins by eating apples. Not yummy: at 250 points (about 50 golden apples, ~1000 segments in the
# small room) the bot bites its tail at 70-200 points, while a person won it at the first try (playtest).
LEVELS = ("classic", "hunger", "hunted", "armed", "prey", "burrows", "alpha", "turrets", "swarm", "ice", "minefield")

HUNT_LENGTH = 16  # segments: shorter, the bot eats before it hunts
STOCK = 24  # shots: fewer, a short bot fetches weapons before it eats (more would be chasing every pickup forever)
WARY = 32  # px: pickups this close to a hostile entity (a turret) are left for last
food = nearest(Apple, GoldenApple, Critter, wary=WARY)
guns = nearest(WeaponPickup, wary=WARY)
# turrets aren't hunted (driving at one runs into its shots), only shot at when they come into the line of fire
foes = nearest(*(cls for cls in ENTITY_NAMES.values() if cls.hostile and cls is not Turret), clearance=0)


def target(snake, map):
    """What the level asks to collect first (the exit last); without ammo a weapon (or food); while short, a stock of
    ammo and then food, until long enough to afford a bite; then the hunt."""
    # what is to be shot (destroy_all) is hunted like any foe, below
    wanted = [goal.entity_cls for goal in map.goals if type(goal) is CollectAllGoal]
    if wanted and (goal := nearest(*wanted, clearance=0)(snake, map)):
        return goal
    # the exit, once all else is done
    exits = [goal for goal in map.goals if isinstance(goal, ExitGoal)]
    if exits and all(goal.done(map, snake) for goal in map.goals if goal not in exits):
        centres = [map.tile_center(tile) for goal in exits for tile in goal.tiles(map)]
        return min(centres, key=lambda pos: (pos - snake.head.pos).length(), default=None)
    if snake.weapon is None or snake.weapon.ammo <= 0:
        return guns(snake, map) or food(snake, map)
    if len(snake) < HUNT_LENGTH:
        return (snake.weapon.ammo < STOCK and guns(snake, map)) or food(snake, map)
    if getattr(snake.weapon, "DROPS", False):  # mines: lead what follows the trail over them
        return food(snake, map)
    # the boss first, then what the level asks to destroy (nests), then the foes they send out
    if map.boss is not None and (body := map.boss.target()) is not None:
        return body
    targets = [goal.entity_cls for goal in map.goals if isinstance(goal, DestroyAllGoal)]
    aimed = nearest(*targets, clearance=0)(snake, map) if targets else None
    return aimed or foes(snake, map) or food(snake, map)


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
