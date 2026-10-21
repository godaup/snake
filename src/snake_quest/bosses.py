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

    def danger(self) -> "tuple[Vec2, float] | None":
        """A spot (centre, radius) for bots to keep away from, e.g. where something is about to land."""
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


class BroodMotherBoss(Boss):
    """The Brood Mother (level 25): a giant spider (the BroodMother entity) in her lair at `pos` with `health`; the bar
    is her health. First she hangs there out of reach (shots glance off), guarded by `sacs` egg sacs about the cave,
    each sending out spiderlings every `call` seconds while the snake is near; every sac destroyed (shot, or burnt by a
    flare) costs her a share of a third of her health. Then (phases by `below`, like the Alpha's) she climbs into the
    dark: every `drop` seconds her shadow grows for `warn` seconds where the snake's head is heading, and she lands
    there, crushing what lies under her (`snake.wound`: half the snake for its head) and spinning webs around her. For
    `stun` seconds she is down and dazed, the only time shots hurt her; then she climbs again. Phases may set `hatch`
    (spiderlings that hatch where she lands) and `dim` (the cave's light shrinks from `light[0]` to `light[1]`).

        boss: {type: brood, pos: [x, y], health: 12, sacs: 4, call: 7, drop: 6, warn: 1.5, stun: 2.5, hatch: 0,
               light: [64, 44], phases: [{below: 1}, {below: 0.67}, {below: 0.34, drop: 4.5, hatch: 2, dim: true}]}"""

    key = "brood"
    title = "THE BROOD MOTHER"
    pressure = ("health", "sacs", "hatch")
    relief = ("call", "drop", "warn", "stun")
    lights = ("light",)
    CRUSH = 12  # px from her centre
    WEB_RING = (2.5, 3.5)  # tiles: webs she spins around where she lands
    SAC_SPACING = 96  # px between the sacs and from her lair

    def __init__(self, cfg, map):
        super().__init__(cfg, map)
        from snake_quest.caves import BroodMother, EggSac, Spiderling

        self._sac, self._spiderling = EggSac, Spiderling
        self.mother = BroodMother.at_pos(Vec2(*cfg.pos) - Vec2(8, 8))
        self.mother.health = self.full = max(1, round(cfg.health))
        map.entities.append(self.mother)
        clear = [[*cfg.pos, self.SAC_SPACING]]
        self.sacs = []
        for _ in range(max(1, round(cfg.sacs))):
            sac = EggSac.at_pos(self._open_spot(map, clear))
            sac.SPAWN = self.setting("call")
            clear.append([sac.pos.x + 4, sac.pos.y + 4, self.SAC_SPACING])
            self.sacs.append(sac)
        map.entities.extend(self.sacs)
        self.sac_damage = self.full / 3 / len(self.sacs)
        self.burst = 0  # sacs destroyed so far
        self.left = 0.0  # seconds until the next step of the drop
        self.target_pos: Vec2 | None = None

    SAC_ROOM = 24  # px of open floor around a sac: room to shoot it from any side

    def _open_spot(self, map, clear) -> Vec2:
        """A free spot (see `map.new_pos`) with open floor SAC_ROOM px around it, if one turns up in a few tries."""
        for _ in range(50):
            pos = map.new_pos(clear=clear)
            centre = pos + Vec2(4, 4)
            ring = [Vec2(pyxel.cos(a), pyxel.sin(a)) * self.SAC_ROOM + centre for a in range(0, 360, 30)]
            if not any(map.check_on_wall(point) or not map.clear_line(centre, point) for point in ring):
                return pos
        return pos

    def next_phase_due(self, map, snake):
        return self.mother.health <= self.full * self.phases[self.phase + 1]["below"] + 1e-6

    def on_phase(self, map, snake):
        if self.mother.state == "hang":
            self.mother.state, self.left = "ceiling", self.setting("drop")

    def _light(self, map) -> None:
        if map.darkness is not None and "light" in self.cfg:
            full, dim = self.setting("light")
            map.darkness.light = dim if self.phases[self.phase].get("dim", False) else full

    def act(self, map, snake, seconds):
        self._light(map)
        burst = sum(not sac.alive for sac in self.sacs)
        if burst > self.burst:  # her brood is lost: it hurts her
            self.mother.health -= (burst - self.burst) * self.sac_damage
            self.burst = burst
            self.mother.flash = self.mother.FLASH
            map.game.sm.effect("hurt")
        if self.mother.health <= 0 and self.mother.alive:
            self.mother.alive, self.mother.killed = False, True
        mother = self.mother
        if mother.state == "hang" or not mother.alive:
            return
        self.left -= seconds
        if mother.state == "ceiling" and self.left <= 0:
            self._aim(map, snake)
            mother.state, self.left = "shadow", self.setting("warn")
        elif mother.state == "shadow":
            mother.shadow = 1 - max(self.left, 0) / self.setting("warn")
            if self.left <= 0:
                self._land(map, snake)
                mother.state, self.left = "rest", self.setting("stun")
        elif mother.state == "rest" and self.left <= 0:
            mother.state, self.left = "ceiling", self.setting("drop")

    def _aim(self, map, snake) -> None:
        """Where she will land: where the head will be when she does, if that is open floor, else where it is."""
        velocity = Vec2(pyxel.cos(snake.heading), pyxel.sin(snake.heading)) * snake.effective_speed
        ahead = snake.head.pos + velocity * (self.setting("warn") * map.game.cfg.fps)
        spot = ahead if not map.check_on_wall(ahead) else snake.head.pos
        self.mother.pos = spot - Vec2(8, 8)
        self.mother.shadow = 0.0

    def _land(self, map, snake) -> None:
        centre = self.mother.center
        map.game.sm.effect("boom")
        index = snake.segment_at(centre, self.CRUSH - snake.size)
        if index is not None:
            map.game.sm.effect("hurt")
            if not snake.wound(index):
                map.snake_killed = True
        x, y = map.tile_xy(centre)
        low, high = self.WEB_RING
        reach = int(high) + 1
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                if low <= (dx * dx + dy * dy) ** 0.5 <= high and pyxel.rndf(0, 1) < 0.5:
                    tile = (x + dx, y + dy)
                    if not any(map.tile_xy(seg.pos) == tile for seg in snake.segs):
                        map.spin_web(tile)
        for _ in range(round(self.phases[self.phase].get("hatch", self.cfg.get("hatch", 0)))):
            young = self._spiderling.at_pos(centre - Vec2(4, 4) + Vec2(pyxel.rndf(-6, 6), pyxel.rndf(-6, 6)))
            map.entities.append(young)

    def bar(self, map, snake):
        return max(self.mother.health, 0) / self.full

    def phase_message(self):
        return "THE BROOD MOTHER CLIMBS INTO THE DARK" if self.phase == 1 else "THE BROOD MOTHER SHROUDS THE CAVE"

    def defeated(self, map):
        return not self.mother.alive

    def target(self):
        """An egg sac while any stands, else her while she is down."""
        sac = next((sac for sac in self.sacs if sac.alive), None)
        if sac is not None:
            return sac.pos + Vec2(4, 4)
        return self.mother.center if self.mother.alive and self.mother.state == "rest" else None

    def danger(self) -> "tuple[Vec2, float] | None":
        """Where she is about to land, for bots to keep away from."""
        if self.mother.state == "shadow":
            return self.mother.center, self.CRUSH + 6
        return None


class MothershipBoss(Boss):
    """The Mothership (level 30): the Mothership entity flies its course (`path`: [x, y] waypoints, a loop) at `speed`
    px per frame, with `health`; the bar is its health. Phase by phase (by `below`, like the Core's):

    1. Three engine pods ride on it (EnginePod turrets, firing every `reload` s) and keep its shield up; each pod
       destroyed costs it a ninth of its health.
    2. Its bay opens for `open` s, then shuts for `closed` s: open, shots hurt it, and every `call` s it drops a raider
       while fewer than `swarm` are about.
    3. As 2, slower (`speed` per phase), and its tractor beam pulls the snake's heading towards it with `pull` (like a
       planet's mass) within `reach` px.

        boss: {type: mothership, path: [[x, y], ...], speed: 0.6, health: 12, reload: 3, open: 4, closed: 3,
               call: 4, swarm: 3, pull: 0, reach: 140,
               phases: [{below: 1}, {below: 0.67}, {below: 0.34, speed: 0.4, pull: 2500}]}"""

    key = "mothership"
    title = "THE MOTHERSHIP"
    pressure = ("health", "swarm", "pull")
    relief = ("call", "reload", "closed")
    PODS = ((-20, 5), (20, 5), (0, -13))  # px from its centre: an engine at each end, one on top (clear of the hull)

    def __init__(self, cfg, map):
        super().__init__(cfg, map)
        from snake_quest.space import EnginePod, Mothership, Raider

        self._raider = Raider
        self.path = [Vec2(*point) for point in cfg.path]
        self.ship = Mothership.at_pos(self.path[0] - Vec2(16, 8))
        self.ship.health = self.full = max(1, round(cfg.health))
        self.ship.reach = self.setting("reach")
        map.entities.append(self.ship)
        self.waypoint = 1
        self.pods = []
        for dx, dy in self.PODS:
            pod = EnginePod.at_pos(self.ship.center + Vec2(dx - 4, dy - 4))
            pod.RELOAD = self.setting("reload")
            self.pods.append(pod)
        map.entities.extend(self.pods)
        self.lost = 0  # pods destroyed so far
        self.left = self.setting("closed")  # seconds until the bay opens or shuts
        self.call_left = self.setting("call")

    def next_phase_due(self, map, snake):
        return self.ship.health <= self.full * self.phases[self.phase + 1]["below"] + 1e-6

    def act(self, map, snake, seconds):
        ship = self.ship
        if not ship.alive:
            return
        # fly the course
        goal = self.path[self.waypoint]
        to_goal = goal - ship.center
        speed = self.setting("speed") * map.game.difficulty.speed
        if to_goal.length() <= speed:
            self.waypoint = (self.waypoint + 1) % len(self.path)
        else:
            ship.pos = ship.pos + to_goal * (speed / to_goal.length())
        for pod, (dx, dy) in zip(self.pods, self.PODS, strict=True):
            pod.pos = ship.center + Vec2(dx - 4, dy - 4)
        lost = sum(not pod.alive for pod in self.pods)
        if lost > self.lost:
            ship.health -= (lost - self.lost) * self.full / 9
            self.lost = lost
            ship.flash = ship.FLASH
        ship.shielded = lost < len(self.pods)
        if ship.health <= 0:
            ship.alive, ship.killed = False, True
            return
        ship.tractor = self.setting("pull")
        if ship.shielded:
            return
        # the bay
        self.left -= seconds
        if self.left <= 0:
            ship.open = not ship.open
            self.left = self.setting("open") if ship.open else self.setting("closed")
        self.call_left -= seconds
        if ship.open and self.call_left <= 0:
            self.call_left = self.setting("call")
            if sum(ent.alive and isinstance(ent, self._raider) for ent in map.entities) < round(self.setting("swarm")):
                map.entities.append(self._raider.at_pos(ship.center - Vec2(4, 4)))

    def bar(self, map, snake):
        return max(self.ship.health, 0) / self.full

    def phase_message(self):
        return "THE MOTHERSHIP OPENS ITS BAY" if self.phase == 1 else "THE MOTHERSHIP LOCKS ON"

    def defeated(self, map):
        return not self.ship.alive

    def target(self):
        """An engine pod while any stands, then the ship while its bay is open."""
        pod = next((pod for pod in self.pods if pod.alive), None)
        if pod is not None:
            return pod.center
        return self.ship.center if self.ship.alive and self.ship.open else None

    def danger(self):
        """The ship's hull, with room around it: bots never cut across its course."""
        return (self.ship.center, 24) if self.ship.alive else None


BOSSES: dict[str, type[Boss]] = {
    cls.key: cls for cls in [Hunger, AlphaBoss, CoreBoss, OuroborosBoss, BroodMotherBoss, MothershipBoss]
}


def load_boss(cfg, map: "Map") -> Boss:
    if cfg.type not in BOSSES:
        raise ValueError(f"unknown boss type {cfg.type!r}, expected one of {sorted(BOSSES)}")
    return BOSSES[cfg.type](cfg, map)
