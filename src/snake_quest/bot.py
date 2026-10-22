"""Let a bot play levels, for balancing (tools/balance.py) and the winnability tests: a PathController heading for the
nearest apple, or with ammo for the nearest hostile entity, or without for a gun lying around (see `target`). `game`
is anything the running state can run on without a window (the tests' FakeGame, the tool's BotGame): it needs `cfg`,
`campaign`, `level_counter`, `score`, `dt`, `difficulty`, `profile`, `sm`, `change_state()` recording into
`requested_states`."""

from collections import Counter

import omegaconf
import pyxel

from snake_quest.controls import PathController, nearest
from snake_quest.entity import ENTITY_NAMES, Apple, Critter, GoldenApple, Turret, WeaponPickup
from snake_quest.goals import CollectAllGoal, DefeatGoal, DestroyAllGoal, ExitGoal, LengthGoal, OxygenGoal, ScoreGoal
from snake_quest.keeper import HandBot
from snake_quest.space import AirTank
from snake_quest.states import StateID
from snake_quest.states.running import RunningStateHandler

# the levels the bot wins by eating apples. Not yummy: at 250 points (about 50 golden apples, ~1000 segments in the
# small room) the bot bites its tail at 70-200 points, while a person won it at the first try (playtest).
LEVELS = (
    "classic",
    "hunger",
    "hunted",
    "armed",
    "prey",
    "burrows",
    "alpha",
    "turrets",
    "swarm",
    "ice",
    "minefield",
    "core",
    "trail",
    "mirror",
    "armored",
    "gauntlet",
    "ouroboros",
    "webs",
    "moles",
    "collapse",
    "bats",
    "brood",
    "airlock",
    "zerog",
    "gravity",
    "asteroids",
    "mothership",
    "crates",
    "plates",
    "keys",
    "conveyors",
    "clockwork",
    "hedges",
    "orchard",
    "lures",
    "lanterns",
    "crow",
)

HUNT_LENGTH = 16  # segments: shorter, the bot eats before it hunts
STOCK = 24  # shots: fewer, a short bot fetches weapons before it eats (more would be chasing every pickup forever)
WARY = 32  # px: pickups this close to a hostile entity (a turret) are left for last
food = nearest(Apple, GoldenApple, Critter, wary=WARY)
guns = nearest(WeaponPickup, wary=WARY)
tanks = nearest(AirTank)  # in the open first, like food
AIR = 0.45  # oxygen below this share: fetch a tank first
# turrets aren't hunted (driving at one runs into its shots), only shot at when they come into the line of fire;
# armoured ones only with a weapon that pierces
foes = nearest(*(cls for cls in ENTITY_NAMES.values() if cls.hostile and cls is not Turret), clearance=0)
soft_foes = nearest(
    *(cls for cls in ENTITY_NAMES.values() if cls.hostile and cls is not Turret),
    clearance=0,
    exclude=tuple(cls for cls in ENTITY_NAMES.values() if cls.armored),
)


def target(snake, map):
    """What the level asks to collect first (the exit last); without ammo a weapon (or food); while short, a stock of
    ammo and then food, until long enough to afford a bite; then the hunt."""
    # a puzzle: the steps of its solution (the level's plan, see workshop.Plan) before anything else
    works = getattr(map, "works", None)
    if works is not None and works.plan is not None and (step := works.plan.target(snake, map)) is not None:
        return step
    # short of air: a tank first
    if any(isinstance(goal, OxygenGoal) and goal.left < AIR for goal in map.goals) and (tank := tanks(snake, map)):
        return tank
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
    if getattr(snake.weapon, "PULLS", False):  # the Tractor hurts nothing: eat (it pulls the food in)
        return food(snake, map)
    if len(snake) < HUNT_LENGTH:  # (another kind of weapon would replace this one, not add to its ammo)
        return (snake.weapon.ammo < STOCK and more_ammo(snake, map)) or food(snake, map)
    if getattr(snake.weapon, "DROPS", False):  # mines: lead what follows the trail over them
        return food(snake, map)
    # nothing to win by fighting while growing is still to do: eat (and shoot what comes into the line of fire)
    fights = map.boss is not None or any(isinstance(goal, (DefeatGoal, DestroyAllGoal)) for goal in map.goals)
    grows = any(isinstance(goal, (LengthGoal, ScoreGoal)) and not goal.done(map, snake) for goal in map.goals)
    if grows and not fights:
        return food(snake, map)
    # the boss first, then what the level asks to destroy (nests), then the foes they send out
    if map.boss is not None and (body := map.boss.target()) is not None:
        return body
    # a boss out of reach for now (the Brood Mother up in the dark): stock up for when it comes down
    if map.boss is not None and snake.weapon.ammo < STOCK and (more := more_ammo(snake, map)):
        return more
    targets = [goal.entity_cls for goal in map.goals if isinstance(goal, DestroyAllGoal)]
    aimed = nearest(*targets, clearance=0)(snake, map) if targets else None
    hunted = foes if getattr(snake.weapon, "PIERCE", False) else soft_foes
    return aimed or hunted(snake, map) or food(snake, map)


def more_ammo(snake, map):
    """The nearest pickup of the weapon the snake carries."""
    kinds = [
        cls
        for cls in ENTITY_NAMES.values()
        if issubclass(cls, WeaponPickup) and type(snake.weapon).__name__ == cls.WEAPON
    ]
    return nearest(*kinds, wary=WARY)(snake, map) if kinds else None


def play(game, level: str, seed: int, seconds: float, hand: bool = True) -> tuple[str, float]:
    """One run of `level`: ("won" | "wall" | "tail" | "killed" | "timeout", seconds played). In the Keeper's levels the
    pet plays as it does for people, and a HandBot keeps the garden (nobody without `hand`)."""
    pyxel.rseed(seed)
    game.level_counter = game.campaign.resolve(level)
    game.requested_states.clear()
    game.score = 0
    running = RunningStateHandler(game)
    if running.map.hand is not None:
        plan = omegaconf.OmegaConf.to_container(running.map.cfg.get("keeper", []))
        running.map.hand.player = HandBot(plan) if hand else None
    else:
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


def win_rate(game, level: str, seeds, seconds: float, hand: bool = True) -> tuple[float, list[float], Counter]:
    """Fraction of runs won, the play times of the wins and the outcomes of all runs."""
    outcomes, wins = Counter(), []
    for seed in seeds:
        outcome, elapsed = play(game, level, seed, seconds, hand)
        outcomes[outcome] += 1
        if outcome == "won":
            wins.append(elapsed)
    return len(wins) / len(seeds), wins, outcomes
