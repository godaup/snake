"""Difficulty levels. Medium is the reference every level is tuned for; the others scale a level's numbers when it loads
(`apply`), with the factors from the `difficulty` section of settings.yaml:

    speed    the snake's speed
    goals    goal targets (score, length, hold length and time, survive, defeat); time limits are divided by it
    helpful  intervals of timers spawning something good (apples, fireflies): larger is rarer
    hostile  intervals of timers spawning something bad (`Entity.hostile`, e.g. enemies): smaller is more often
    boss     a boss's pressure (`Boss.pressure` keys, e.g. The Hunger's rise); its `relief` keys are divided by it
    light    light radii in dark levels

The Keeper's tool budgets (`hand`) are divided by the goals factor, rounded up: easier gives more.

Where scaling isn't enough, a level sets absolute values per difficulty, merged over the scaled level:

    difficulty:
      hard: {goal: {score: 70}}
"""

import math
from dataclasses import dataclass

import omegaconf

NAMES = ("easy", "medium", "hard", "nightmare")
DEFAULT = "medium"
# goals with a number to scale: key -> the scaled fields (None: the value itself)
SCALED_GOALS = {
    "score": None,
    "length": None,
    "survive": None,
    "defeat": None,
    "hold_length": ("length", "seconds"),
    "collapse": ("speed",),  # the cave-in comes faster
}
LIMITS = ("time_limit",)  # goals that get easier with more: divided by the goals factor
LIMIT_FIELDS = {"oxygen": ("drain",)}  # the same for fields of a goal


@dataclass(frozen=True)
class Difficulty:
    name: str
    speed: float = 1.0
    goals: float = 1.0
    helpful: float = 1.0
    hostile: float = 1.0
    boss: float = 1.0
    light: float = 1.0

    @property
    def label(self) -> str:
        return self.name.upper()


def load(settings, name: str) -> Difficulty:
    """The named difficulty with its factors from settings (`settings.difficulty`); unknown names fall back to the
    default."""
    if name not in NAMES:
        name = DEFAULT
    factors = settings.get("difficulty", {}).get(name, {})
    return Difficulty(name=name, **factors)


def next_name(name: str, step: int = 1) -> str:
    """The difficulty `step` places further in NAMES (wrapping), e.g. for the menu."""
    index = NAMES.index(name) if name in NAMES else NAMES.index(DEFAULT)
    return NAMES[(index + step) % len(NAMES)]


def _round(value: float, like) -> float | int:
    """Scaled value of the same kind as the original: whole numbers stay whole (at least 1)."""
    return max(1, round(value)) if isinstance(like, int) else value


def apply(cfg: omegaconf.DictConfig, difficulty: Difficulty) -> omegaconf.DictConfig:
    """A copy of a level's config with its numbers scaled for `difficulty`, plus the level's own overrides."""
    # imported here: the command line uses NAMES before anything touches pyxel
    from snake_quest.bosses import BOSSES
    from snake_quest.entity import ENTITY_NAMES

    cfg = omegaconf.OmegaConf.create(omegaconf.OmegaConf.to_container(cfg))
    d = difficulty
    for key, fields in SCALED_GOALS.items():
        if key not in cfg.get("goal", {}):
            continue
        if fields is None:
            cfg.goal[key] = _round(cfg.goal[key] * d.goals, cfg.goal[key])
        else:
            for name in fields:
                cfg.goal[key][name] = _round(cfg.goal[key][name] * d.goals, cfg.goal[key][name])
    for key in LIMITS:
        if key in cfg.get("goal", {}):
            cfg.goal[key] = cfg.goal[key] / d.goals
    for key, fields in LIMIT_FIELDS.items():
        for name in fields if key in cfg.get("goal", {}) else ():
            cfg.goal[key][name] = cfg.goal[key][name] / d.goals
    for timer in cfg.get("timers", {}).values():
        if timer.callback.type != "spawn":
            continue
        factor = d.hostile if ENTITY_NAMES[timer.callback.entity].hostile else d.helpful
        timer.duration = timer.duration * factor
        timer.frequency = timer.frequency * factor
    for tool in cfg.get("hand", {}):
        cfg.hand[tool] = max(0, math.ceil(cfg.hand[tool] / d.goals))
    if "darkness" in cfg:
        cfg.darkness.light = cfg.darkness.light * d.light
    if "boss" in cfg:
        boss_cls = BOSSES[cfg.boss.type]
        for section in [cfg.boss, *cfg.boss.get("phases", [])]:
            for key in boss_cls.pressure:
                if key in section:
                    section[key] = section[key] * d.boss
            for key in boss_cls.relief:
                if key in section:
                    section[key] = section[key] / d.boss
            for key in boss_cls.lights:
                if key in section:
                    section[key] = [radius * d.light for radius in section[key]]
    overrides = cfg.get("difficulty", {}).get(d.name)
    if overrides is not None:
        cfg = omegaconf.OmegaConf.merge(cfg, overrides)
    return cfg
