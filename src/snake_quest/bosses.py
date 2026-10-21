"""Bosses, built from the optional `boss` section of a level file: `boss: {type: <key>, phases: [...], ...}`.

A boss has a bar (0..1, drawn at the top of the play area by the HUD) and phases. By default a phase starts `after`
seconds of play; each phase is a dict of settings the boss reads through `self.setting(name)`, falling back to the
boss section itself. The level's goals decide when it is won (e.g. `hold_length` for The Hunger)."""

import datetime
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import pyxel

from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake

ROMAN = ["I", "II", "III", "IV", "V"]


class Boss(ABC):
    key: ClassVar[str]
    title: ClassVar[str]  # upper case, shown on the bar
    # settings harder difficulties raise (pressure), lower (relief) or apply to light radii, see difficulty.py
    pressure: ClassVar[tuple[str, ...]] = ()
    relief: ClassVar[tuple[str, ...]] = ()
    lights: ClassVar[tuple[str, ...]] = ()

    def __init__(self, cfg, map: "Map"):
        self.cfg = cfg
        self.phases: list = list(cfg.get("phases", [{"after": 0}]))
        self.phase = 0
        self.elapsed = 0.0  # seconds of play
        self.since_phase = 0.0  # seconds since the current phase started, e.g. for the HUD's banner

    def setting(self, name: str):
        """A value from the current phase, or from the boss section when the phase doesn't set it."""
        phase = self.phases[self.phase]
        return phase[name] if name in phase else self.cfg[name]

    def update(self, map: "Map", snake: "Snake", dt: datetime.timedelta) -> None:
        seconds = dt.total_seconds()
        self.elapsed += seconds
        self.since_phase += seconds
        if self.phase + 1 < len(self.phases) and self.next_phase_due(map, snake):
            self.phase += 1
            self.since_phase = 0.0
            self.on_phase(map, snake)
        self.act(map, snake, seconds)

    def next_phase_due(self, map: "Map", snake: "Snake") -> bool:
        """Whether to move on to the next phase; by time unless a boss decides otherwise (e.g. by its health)."""
        return self.elapsed >= self.phases[self.phase + 1]["after"]

    def on_phase(self, map: "Map", snake: "Snake") -> None:  # noqa: B027 (optional hook)
        """Called when a new phase starts."""

    @abstractmethod
    def act(self, map: "Map", snake: "Snake", seconds: float) -> None:
        """What the boss does every frame."""

    @abstractmethod
    def bar(self, map: "Map", snake: "Snake") -> float:
        """Fill of the boss bar, 0..1."""

    def label(self) -> str:
        """Text next to the bar: the title, with the phase number once there is more than one phase."""
        return self.title if len(self.phases) == 1 else f"{self.title} {ROMAN[self.phase]}"

    def phase_message(self) -> str | None:
        """Shown big for a moment when a phase starts (not the first)."""
        return None

    def defeated(self, map: "Map") -> bool:
        """Whether the boss is beaten (see the `boss: defeated` goal)."""
        return False

    def target(self) -> "Vec2 | None":
        """Where to shoot at, for bots: the boss's body if it has one."""
        return None


class Hunger(Boss):
    """The Hunger (level 5): hunger rises all the time and the snake shrinks the hungrier it is, down to nothing;
    every meal (an entity eaten, not killed) eases it. The hungrier, the smaller the light around the head.

        boss: {type: hunger, rise: 0.05, meal: 0.4, starve: 3, light: [48, 20], phases: [{after: 0}, ...]}

    `rise`: hunger per second, `meal`: hunger a meal takes away, `starve`: segments lost per second at full hunger,
    `light`: radius of the head's light when full and when starving (needs `darkness`)."""

    key = "hunger"
    title = "THE HUNGER"
    pressure = ("rise", "starve")
    relief = ("meal",)
    lights = ("light",)

    def __init__(self, cfg, map):
        super().__init__(cfg, map)
        self.hunger = 0.0
        self.eaten = map.eaten
        self.starving = 0.0  # segments lost but not cut yet (shrinking is slower than one per frame)

    def act(self, map, snake, seconds):
        meals, self.eaten = map.eaten - self.eaten, map.eaten
        self.hunger = min(1.0, max(0.0, self.hunger + self.setting("rise") * seconds - meals * self.setting("meal")))
        self.starving += self.hunger * self.setting("starve") * seconds
        while self.starving >= 1:
            self.starving -= 1
            if not snake.cut(1):
                map.snake_killed = True  # starved
                break
        if map.darkness is not None:
            full, starving = self.setting("light")
            map.darkness.light = full + (starving - full) * self.hunger

    def bar(self, map, snake):
        return self.hunger

    def phase_message(self):
        return "THE HUNGER GROWS"


class AlphaBoss(Boss):
    """The Alpha (level 10): puts the Alpha (entity) into the level at `pos` with `health`; the bar is its health. Every
    `call` seconds it calls a hunting beetle out of one of the level's nests, as long as fewer than `pack` are about, so
    destroying the nests stops the reinforcements. Phases start when its health falls `below` a fraction, and can set
    its `speed`.

        boss: {type: alpha, pos: [x, y], health: 12, call: 8, pack: 4, phases: [{below: 1}, {below: 0.66, call: 6}]}"""

    key = "alpha"
    title = "THE ALPHA"
    pressure = ("health", "pack")
    relief = ("call",)

    def __init__(self, cfg, map):
        super().__init__(cfg, map)
        from snake_quest.entity import Alpha, Hunter, Nest

        self._hunter, self._nest = Hunter, Nest
        self.alpha = Alpha.at_pos(Vec2(*cfg.pos) - Vec2(8, 8))
        self.alpha.health = self.full = max(1, round(cfg.health))
        map.entities.append(self.alpha)
        self.left = self.setting("call")

    def next_phase_due(self, map, snake):
        return self.alpha.health <= self.full * self.phases[self.phase + 1]["below"]

    def act(self, map, snake, seconds):
        if "speed" in self.phases[self.phase]:
            self.alpha.SPEED = self.setting("speed")
        self.left -= seconds
        if self.left > 0 or not self.alpha.alive:
            return
        self.left = self.setting("call")
        nests = [ent for ent in map.entities if ent.alive and isinstance(ent, self._nest)]
        pack = sum(ent.alive and type(ent) is self._hunter for ent in map.entities)
        if nests and pack < round(self.setting("pack")):
            nest = nests[pyxel.rndi(0, len(nests) - 1)]
            beetle = self._hunter.at_pos(Vec2(nest.pos.x, nest.pos.y))
            beetle.asleep = False
            map.entities.append(beetle)

    def bar(self, map, snake):
        return max(self.alpha.health, 0) / self.full

    def phase_message(self):
        return "THE ALPHA CALLS ITS PACK"

    def defeated(self, map):
        return not self.alpha.alive

    def target(self):
        return self.alpha.center if self.alpha.alive else None


class CoreBoss(Boss):
    """The Core (level 15): puts the Core (entity) into the level at `pos` with `health`; the bar is its health. It is
    shielded while any turret of its ring stands: each phase builds a new ring of `turrets` turrets `ring` px around it
    (firing every `reload` seconds, `armor` shots each), and phases start when its health falls `below` a fraction.
    Every `call` seconds it launches a drone, as long as fewer than `swarm` are about.

        boss: {type: core, pos: [x, y], health: 6, turrets: 3, ring: 64, reload: 5, armor: 1, call: 12, swarm: 1,
               phases: [{below: 1}, {below: 0.66, turrets: 4}, {below: 0.33, turrets: 4, reload: 4}]}"""

    key = "core"
    title = "THE CORE"
    pressure = ("health", "turrets", "swarm")
    relief = ("call",)

    def __init__(self, cfg, map):
        super().__init__(cfg, map)
        from snake_quest.entity import Core, Drone, Turret

        self._drone, self._turret = Drone, Turret
        self.core = Core.at_pos(Vec2(*cfg.pos) - Vec2(8, 8))
        self.core.health = self.full = max(1, round(cfg.health))
        map.entities.append(self.core)
        self.ring: list = []
        self.left = self.setting("call")
        self._build(map)

    def _build(self, map: "Map") -> None:
        """A new ring of turrets around the core, which raises its shield again."""
        count, radius, centre = max(1, round(self.setting("turrets"))), self.setting("ring"), self.core.center
        offset = pyxel.rndf(0, 360)
        self.ring = []
        for index in range(count):
            angle = offset + 360 * index / count
            turret = self._turret.at_pos(centre + Vec2(pyxel.cos(angle), pyxel.sin(angle)) * radius - Vec2(4, 4))
            turret.RELOAD = self.setting("reload")
            turret.health = max(1, round(self.setting("armor")))
            self.ring.append(turret)
        map.entities.extend(self.ring)
        self.core.shielded = True

    def next_phase_due(self, map, snake):
        return self.core.health <= self.full * self.phases[self.phase + 1]["below"]

    def on_phase(self, map, snake):
        self._build(map)

    def act(self, map, snake, seconds):
        self.core.shielded = any(turret.alive for turret in self.ring)
        self.left -= seconds
        if self.left > 0 or not self.core.alive:
            return
        self.left = self.setting("call")
        if sum(ent.alive and isinstance(ent, self._drone) for ent in map.entities) < round(self.setting("swarm")):
            map.entities.append(self._drone.at_pos(Vec2(self.core.pos.x + 4, self.core.pos.y + 4)))

    def bar(self, map, snake):
        return max(self.core.health, 0) / self.full

    def phase_message(self):
        return "THE CORE REBUILDS ITS DEFENCES"

    def defeated(self, map):
        return not self.core.alive

    def target(self):
        """The core once its shield is down, else a turret of its ring."""
        if not self.core.alive:
            return None
        if not self.core.shielded:
            return self.core.center
        return next((turret.center for turret in self.ring if turret.alive), None)


class OuroborosBoss(Boss):
    """Ouroboros (level 20): a rival snake (the Rival entity) with `lives`, starting from its lair at `pos`, moving at
    `speed` and `length` segments long at every start, shooting every `reload` seconds at most; it is back `respawn`
    seconds after losing a life. The bar is its lives (the current one by its length). Phases start when its lives
    fall `below` a fraction and may change these settings (from its next start).

        boss: {type: ouroboros, pos: [x, y], lives: 3, speed: 1.2, length: 16, reload: 1.2, respawn: 3,
               phases: [{below: 1}, {below: 0.67, speed: 1.3}, {below: 0.34, speed: 1.4}]}"""

    key = "ouroboros"
    title = "OUROBOROS"
    pressure = ("lives", "speed")
    relief = ("respawn", "reload")

    def __init__(self, cfg, map):
        super().__init__(cfg, map)
        from snake_quest.entity import Rival

        self.rival = Rival.at_pos(Vec2(*cfg.pos) - Vec2(4, 4))
        self.rival.lives = self.full = max(1, round(cfg.lives))
        self._tune()
        self.rival.spawn()
        map.entities.append(self.rival)

    def _tune(self) -> None:
        self.rival.SPEED = self.setting("speed")
        self.rival.START = max(self.rival.MIN, round(self.setting("length")))
        self.rival.RESPAWN = self.setting("respawn")
        self.rival.RELOAD = self.setting("reload")

    def next_phase_due(self, map, snake):
        return self.rival.lives <= self.full * self.phases[self.phase + 1]["below"]

    def on_phase(self, map, snake):
        self._tune()

    def act(self, map, snake, seconds):
        pass  # the rival is an entity: it moves in the map's update

    def bar(self, map, snake):
        body = self.rival.body
        current = min(len(body) / self.rival.START, 1.0) if body is not None else 0.0
        return max(self.rival.lives - 1 + current, 0) / self.full

    def phase_message(self):
        return "OUROBOROS SHEDS ITS SKIN"

    def defeated(self, map):
        return self.rival.lives <= 0

    def target(self):
        """The rival's tail: shots there cut it, and the head (deadly to meet) is farthest away."""
        body = self.rival.body
        return body.segs[-1].pos if body is not None and self.rival.lives > 0 else None


BOSSES: dict[str, type[Boss]] = {cls.key: cls for cls in [Hunger, AlphaBoss, CoreBoss, OuroborosBoss]}


def load_boss(cfg, map: "Map") -> Boss:
    if cfg.type not in BOSSES:
        raise ValueError(f"unknown boss type {cfg.type!r}, expected one of {sorted(BOSSES)}")
    return BOSSES[cfg.type](cfg, map)
