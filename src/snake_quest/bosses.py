"""Bosses, built from the optional `boss` section of a level file: `boss: {type: <key>, phases: [...], ...}`.

A boss has a bar (0..1, drawn at the top of the play area by the HUD) and phases. By default a phase starts `after`
seconds of play; each phase is a dict of settings the boss reads through `self.setting(name)`, falling back to the
boss section itself. The level's goals decide when it is won (e.g. `hold_length` for The Hunger)."""

import datetime
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import pyxel

from snake_quest.utils import Vec2

CELL = 16  # px: the Workshop's bench grid (see workshop.py)

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake

ROMAN = ["I", "II", "III", "IV", "V"]


class Boss(ABC):
    """A level's boss, built by `load_boss` from the level's `boss` section; subclasses are listed in BOSSES. `update`
    moves through the phases and calls `act` every frame; the HUD draws `bar()` with `title`."""

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
        """One frame: count the time, start the next phase when it is due (`on_phase`) and `act`."""
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

    def solids(self) -> "list[tuple[Vec2, float]]":
        """Circles (centre, radius) bots keep just clear of, however far ahead (what only moves now and then)."""
        return []


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
        """Give the rival the current phase's speed, start length, respawn time and reload time."""
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
        """The light radius for the phase: dimmed where the phase says `dim`."""
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
        """She lands: crushes what lies under her, spins a ring of webs around (not on the snake) and lets the phase's
        `hatch` spiderlings out."""
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


class ClockworkBoss(Boss):
    """The Clockwork (level 35): the Clockwork entity (a 32x32 block that never moves) at `pos` with `health`; the bar
    is its health. Its two hands (`hands`: their lengths) tick round it once a second, `tick` degrees (the short hand a
    quarter of that): what they sweep over or the head runs into is cut there, as by a shot. Its face is shut, so shots
    glint off, except while it is open (`open` seconds). Phase by phase (by `below`, like the Core's):

    1. Jam its gears: with crates on all the red plates (beside it), its hands stop and the face opens; then it throws
       the crates back where they started.
    2. Hold its springs: the crates are gone; with `hold` of the blue plates under the body at once, the face opens.
    3. Its locks: it winds itself shut behind `locks` locks (up to three). Every `call` s it puts out the key the next
       lock needs (where none is about) and a clockwork mouse while fewer than `mice` are about; the head brings a key
       by touching it. With all of them open, the face stays open.

        boss: {type: clockwork, pos: [x, y], health: 9, tick: 6, hands: [96, 64], open: 6, hold: 2, locks: 2, call: 6,
               mice: 2,
               phases: [{below: 1}, {below: 0.67, tick: 9, open: 8}, {below: 0.34}]}

    Bots get a plan from it (see workshop.Plan), made anew whenever the last one is done: the pushes onto the red
    plates, a run over the blue plates, the key to fetch and bring."""

    key = "clockwork"
    title = "THE CLOCKWORK"
    pressure = ("health", "tick", "mice", "hold", "locks")
    relief = ("open", "call")
    REACH = 4  # px from a hand that the head touches it
    HUB = 18  # px from the centre where the hands start (the face)
    DANGER = 10  # px around the points along a hand bots keep clear of (now and up to two ticks on)
    ARMED = 12  # shots: with fewer, bots fetch a weapon before they work the puzzle
    SLACK = 1.4  # times the length a run over the blue plates needs, that bots grow to first
    BURY = 6  # segments bots grow by after picking up a key
    GRACE = 1.0  # seconds
    TOUCH = 4  # px from the clock the head brings a key at

    def __init__(self, cfg, map):
        super().__init__(cfg, map)
        from snake_quest.workshop import KEYS, Clockwork, Mouse

        self._keys, self._mouse = KEYS, Mouse
        self.map = map
        self.clock = Clockwork.at_pos(Vec2(*cfg.pos))
        self.clock.health = self.full = max(1, round(cfg.health))
        map.entities.append(self.clock)
        map.works.crates.append(self.clock)
        self.angles = [270.0, 270.0]  # the long hand and the short one, pointing up (twelve o'clock)
        self.tick_left = 1.0
        self.open_left = 0.0
        self.call_left = self.setting("call")
        self.locks = list(range(min(3, max(1, round(cfg.get("locks", 3))))))  # colours still shut on the face
        self.grace = 0.0  # seconds the hands still spare the snake after striking it
        self._sync()

    def _sync(self) -> None:
        """Pass the hands' angles and lengths, and in phase 3 the locks, to the Clockwork entity for drawing and
        cutting."""
        self.clock.hands = list(zip(self.angles, self.cfg.hands, strict=True))
        self.clock.locks = list(self.locks) if self.phase == 2 else []

    def next_phase_due(self, map, snake):
        return self.clock.health <= self.full * self.phases[self.phase + 1]["below"] + 1e-6

    def on_phase(self, map, snake):
        self.clock.open, self.open_left = False, 0.0
        if self.phase == 1:  # the crates are swept away
            for crate in list(map.works.crates):
                if crate is not self.clock:
                    crate.alive = False
                    map.works.crates.remove(crate)
        map.works.plan = None

    def act(self, map, snake, seconds):
        clock = self.clock
        if not clock.alive:
            return
        if clock.health <= 0:
            clock.alive, clock.killed = False, True
            return
        works = map.works
        self.grace = max(self.grace - seconds, 0.0)
        # the face
        if self.open_left > 0:
            self.open_left -= seconds
            if self.open_left <= 0 and self.phase < 2:
                clock.open = False
                if self.phase == 0:  # it throws the crates back
                    for crate in works.crates:
                        if crate is not clock and works.free(crate, crate.start, snake):
                            crate.pos = Vec2(crate.start.x, crate.start.y)
                works.plan = None
        elif self._unlocked(works):
            self._open()
        elif self.phase == 2:
            self._locks(map, snake, seconds)
        # the hands tick (not while it is jammed open)
        self.tick_left -= seconds
        if self.tick_left <= 0:
            self.tick_left += 1.0
            if not (clock.open and self.phase == 0):
                old = list(self.angles)
                tick = self.setting("tick")
                self.angles = [(self.angles[0] + tick) % 360, (self.angles[1] + tick / 4) % 360]
                for before, after, length in zip(old, self.angles, self.cfg.hands, strict=True):
                    self._sweep(map, snake, before, after, length)
        self._touch(map, snake)
        self._sync()
        if works.plan is None or works.plan.done or (works.plan.index == 0 and works.plan.stage == 0):
            works.plan = self._plan(map, snake)  # (made anew while it hasn't started, e.g. once armed)

    def _open(self) -> None:
        """Open the face for `open` seconds; the bots' plan for the phase is done."""
        self.clock.open, self.open_left = True, self.setting("open")
        self.map.works.plan = None
        self.map.game.sm.effect("win")

    def _unlocked(self, works) -> bool:
        """Whether the puzzle of the phase is solved: all red plates down (1), enough blue ones (2)."""
        if self.phase == 0:
            return self._down(works, 0) == self._plates(works, 0) > 0
        return self.phase == 1 and self._down(works, 1) >= round(self.setting("hold"))

    def _plates(self, works, colour: int) -> int:
        """How many plates of `colour` the level has."""
        return sum(plate_colour == colour for plate_colour, _ in works.plates)

    def _down(self, works, colour: int) -> int:
        """How many plates of `colour` are down."""
        return sum(works.plates[index][0] == colour for index in works.down)

    def _locks(self, map, snake, seconds) -> None:
        """Phase 3: keys and mice come out; a key brought (the head stopped at the clock) opens a lock."""
        works, clock = map.works, self.clock
        if not self.locks:
            clock.open = True
            return
        head, near = snake.head.pos, self.TOUCH
        touching = clock.pos.x - near <= head.x <= clock.pos.x + clock.w + near and (
            clock.pos.y - near <= head.y <= clock.pos.y + clock.h + near
        )
        if touching and works.keys & set(self.locks):
            colour = next(c for c in self.locks if c in works.keys)
            seg = next(seg for seg in snake.segs if seg.key == colour)
            seg.key = None
            works.carried[id(seg)] = (seg, None, seg.pos)
            snake.segs.remove(seg)
            works._recount()
            self.locks.remove(colour)
            works.plan = None
            map.game.sm.effect("portal")
        self.call_left -= seconds
        if self.call_left > 0:
            return
        self.call_left = self.setting("call")
        if (
            self.locks
            and not (set(self.locks) & works.keys)
            and not any(isinstance(ent, self._keys[self.locks[0]]) and ent.alive for ent in map.entities)
        ):
            map.entities.append(self._keys[self.locks[0]].at_pos(map.new_pos(snake=snake, away=64)))
        if sum(isinstance(ent, self._mouse) and ent.alive for ent in map.entities) < round(self.setting("mice")):
            mouse = self._mouse.at_pos(map.new_pos(snake=snake, away=96))
            mouse.asleep = False
            map.entities.append(mouse)

    def _sweep(self, map, snake, before: float, after: float, length: float) -> None:
        """A hand ticked from `before` to `after`: the body in the swept wedge is cut there, the head is the end."""
        center = self.clock.center
        span = (after - before) % 360
        for index, seg in enumerate(snake.segs):
            offset = seg.pos - center
            if not self.HUB <= offset.length() <= length:
                continue
            if (pyxel.atan2(offset.y, offset.x) - before) % 360 <= span:
                self._hurt(map, snake, index)
                return

    def _touch(self, map, snake) -> None:
        """The head running into a hand: as hit there."""
        center, head = self.clock.center, snake.head.pos
        for angle, length in zip(self.angles, self.cfg.hands, strict=True):
            direction = Vec2(pyxel.cos(angle), pyxel.sin(angle))
            along = (head.x - center.x) * direction.x + (head.y - center.y) * direction.y
            if self.HUB <= along <= length and (head - (center + direction * along)).length() < self.REACH:
                self._hurt(map, snake, 0)

    def _hurt(self, map, snake, index: int) -> None:
        """A hand strikes segment `index`: the body is cut there, as by a shot (the head: half of it; the end when the
        snake is too short), and the hands spare it for GRACE seconds."""
        if self.grace > 0:
            return
        self.grace = self.GRACE
        map.game.sm.effect("hurt")
        if not snake.wound(index):
            map.snake_killed = True

    def _plan(self, map, snake):
        """The next errand for bots: the pushes onto the red plates (phase 1), a run over blue plates (2), the key the
        next lock needs and bringing it (3); None while the face is open or there is nothing to do."""
        import omegaconf

        from snake_quest.workshop import DIRECTIONS, Plan

        works = map.works
        if self.clock.open:
            return None
        weapon = snake.weapon
        armed = weapon is not None and weapon.ammo >= self.ARMED
        if not armed and any(ent.alive and hasattr(ent, "WEAPON") for ent in map.entities):
            return None  # a weapon first, for when the face opens
        origin = works.origin

        def cell_of(pos: Vec2) -> tuple[int, int]:
            return int(pos.x - origin.x) // CELL, int(pos.y - origin.y) // CELL

        def plates(colour: int) -> list[tuple[int, int]]:
            return [(min(x for x, _ in t) // 2, min(y for _, y in t) // 2) for c, t in works.plates if c == colour]

        steps = []
        if self.phase == 0:
            pressed = {cell_of(crate.center) for crate in works.crates if crate is not self.clock}
            for plate in plates(0):
                if plate in pressed:
                    continue
                for crate in works.crates:
                    here = cell_of(crate.center)
                    if crate is self.clock or here in plates(0):
                        continue
                    push = next(
                        (
                            [list(here), name, gap]
                            for name, (dx, dy) in DIRECTIONS.items()
                            if (gap := (plate[0] - here[0]) * dx + (plate[1] - here[1]) * dy) > 0
                            and (here[0] + dx * gap, here[1] + dy * gap) == plate
                        ),
                        None,
                    )
                    if push is not None:
                        steps.append({"push": push})
                        break
        elif self.phase == 1:
            run, left = [cell_of(snake.head.pos)], plates(1)
            for _ in range(min(len(left), max(1, round(self.setting("hold"))))):  # the nearest, then the next nearest
                run.append(min(left, key=lambda plate, at=run[-1]: abs(plate[0] - at[0]) + abs(plate[1] - at[1])))
                left.remove(run[-1])
            run = run[1:]
            gap = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(run, run[1:], strict=False)) * CELL
            needed = int(gap / snake.effective_speed * self.SLACK) + 12  # the body must reach over the whole run
            steps = ([{"grow": needed}] if len(snake) < needed else []) + [{"visit": list(plate)} for plate in run]
        elif self.locks:  # the key, a meal or two (it sits deeper, away from the mice), then to the clock
            steps = [
                {"key": Plan.COLOURS[self.locks[0]]},
                {"grow": len(snake) + self.BURY},
                {"bring": list(cell_of(self.clock.center))},
            ]
        if not steps:
            return None
        return Plan(omegaconf.OmegaConf.create([{"reset": None, "steps": steps}]), works)

    def bar(self, map, snake):
        return max(self.clock.health, 0) / self.full

    def phase_message(self):
        return "THE CLOCKWORK SPRINGS LOOSE" if self.phase == 1 else "THE CLOCKWORK WINDS ITSELF SHUT"

    def defeated(self, map):
        return not self.clock.alive

    def target(self):
        """Its face while it is open."""
        return self.clock.center if self.clock.alive and self.clock.open else None

    def solids(self):
        """Points along each hand where it is and will be after the next tick, for bots to keep clear of."""
        center, circles = self.clock.center, []
        tick = self.setting("tick")
        for angle, length, step in zip(self.angles, self.cfg.hands, (tick, tick / 4), strict=True):
            for a in (angle + step * k / 2 for k in range(5)):
                direction = Vec2(pyxel.cos(a), pyxel.sin(a))
                circles += [(center + direction * r, self.DANGER) for r in range(self.HUB, int(length) + 1, 10)]
        return circles


class CrowBoss(Boss):
    """The Crow (level 40, the Keeper's): a Crow entity flying over the garden from `pos`, with `health`; the bar is its
    health. The snake can't shoot: its head bites the Crow only while it is on the ground. Phases by `below`, like the
    Alpha's:

    1. The thief: every `steal` seconds it flies to an apple (of the tree with most apples, if any) and sits on it for
       `perch` seconds, then eats it; without apples it pulls up a hedge the hand planted (`perch` seconds on the
       ground too; the hedge goes back to the hand).
    2. The swoop: every `swoop` seconds it marks a line to where the snake's tail will be (`warn` seconds) and dives
       along it (over the level's walls); a hit cuts `chunk` segments off. A hedge the hand planted (sprouting too) on
       the line stops the dive: it lies stunned for `stun` seconds.
    3. The flock: it goes on swooping and calls a jackdaw every `call` seconds while fewer than `flock` are about; dusk
       falls (the light shrinks from `light[0]` to `light[1]` over DUSK seconds; needs `darkness`).

        boss: {type: crow, pos: [x, y], health: 6, steal: 4, perch: 3, swoop: 6, warn: 1.5, stun: 3, chunk: 8,
               call: 6, flock: 0, light: [400, 56], phases: [{below: 1}, {below: 0.67}, {below: 0.34, flock: 3}]}"""

    key = "crow"
    title = "THE CROW"
    pressure = ("health", "flock", "chunk")
    relief = ("steal", "perch", "swoop", "warn", "stun", "call")
    lights = ("light",)
    FLY = 1.8  # px per frame
    DIVE = 3.5
    STRIKE = 8  # px from its centre to a segment
    DUSK = 20.0  # seconds dusk takes to fall
    DANGER = 10  # px: circles along a swoop's line bots keep out of
    MARGIN = 16  # px from the level's edges where it flies

    def __init__(self, cfg, map):
        super().__init__(cfg, map)
        from snake_quest.keeper import Crow, Jackdaw

        self._jackdaw = Jackdaw
        self.crow = Crow.at_pos(Vec2(*cfg.pos) - Vec2(8, 8))
        self.crow.health = self.full = max(1, round(cfg.health))
        map.entities.append(self.crow)
        self.crow.state = "hover"
        self.left = self.setting("steal")
        self.call_left = self.setting("call")
        self.dest: Vec2 | None = None
        self.prey = None  # the apple or hedge tile it is after
        self.flock: list = []

    def next_phase_due(self, map, snake):
        return self.crow.health <= self.full * self.phases[self.phase + 1]["below"] + 1e-6

    def on_phase(self, map, snake):
        if not self.crow.grounded:
            self._take_off(map, self.setting("swoop") / 2)

    def _light(self, map) -> None:
        """Dusk in the flock phase: the light shrinks from `light[0]` to `light[1]` over DUSK seconds."""
        if map.darkness is None or "light" not in self.cfg:
            return
        full, dusk = self.setting("light")
        share = min(self.since_phase / self.DUSK, 1.0) if self.phase >= 2 else 0.0
        map.darkness.light = full + (dusk - full) * share

    def _sky(self, map) -> Vec2:
        """A random spot in the air over the level."""
        return Vec2(
            pyxel.rndf(self.MARGIN, map.cfg.width - self.MARGIN),
            pyxel.rndf(self.MARGIN, map.cfg.height - self.MARGIN) + map.header,
        )

    def _take_off(self, map, wait: float) -> None:
        """Fly up to a spot in the sky and wait `wait` seconds before the next move."""
        crow = self.crow
        crow.state, crow.line, self.prey = "fly", None, None
        self.dest, self.left = self._sky(map), wait

    def _fly(self, target: Vec2, speed: float) -> bool:
        """One frame towards `target`; True once there."""
        to = target - self.crow.center
        distance = to.length()
        if distance <= speed:
            self.crow.pos = target - Vec2(8, 8)
            return True
        self.crow.pos = self.crow.pos + to * (speed / distance)
        return False

    def act(self, map, snake, seconds):
        self._light(map)
        crow = self.crow
        if not crow.alive:
            return
        speed = map.game.difficulty.speed
        if crow.bitten:  # bitten on the ground: up and away
            crow.bitten = False
            self._take_off(map, self.setting("steal" if self.phase == 0 else "swoop"))
        if self.phase >= 2:
            self._call(map, snake, seconds)
        self.left -= seconds
        if crow.state == "fly":
            target = self.dest if self.prey is None else self._prey_pos(map)
            if target is None:  # what it was after is gone
                self._take_off(map, self.left)
            elif self._fly(target, self.FLY * speed):
                if self.prey is None:
                    crow.state = "hover"
                else:
                    crow.state, self.left = "perch", self.setting("perch")
        elif crow.state == "hover" and self.left <= 0:
            if self.phase == 0:
                self._steal(map)
            else:
                self._mark(map, snake)
        elif crow.state == "perch" and self.left <= 0:
            self._feed(map)
            self._take_off(map, self.setting("steal"))
        elif crow.state == "warn" and self.left <= 0:
            crow.state = "dive"
        elif crow.state == "dive":
            self._dive(map, snake, speed)
        elif crow.state == "stunned" and self.left <= 0:
            self._take_off(map, self.setting("swoop"))

    def _steal(self, map) -> None:
        """Off to an apple (the fullest tree's first), or else to a planted hedge, or once round the garden."""
        from snake_quest.entity import Apple
        from snake_quest.keeper import Tree

        trees = [ent for ent in map.entities if ent.alive and isinstance(ent, Tree) and ent.apples]
        if trees:
            tree = max(trees, key=lambda ent: len(ent.apples))
            self.prey = tree.apples[0]
        else:
            apples = [ent for ent in map.entities if ent.alive and isinstance(ent, Apple)]
            hedges = sorted(map.hand.planted) if map.hand is not None else []
            if apples:
                self.prey = apples[pyxel.rndi(0, len(apples) - 1)]
            elif hedges:
                self.prey = hedges[pyxel.rndi(0, len(hedges) - 1)]
        if self.prey is None:
            self._take_off(map, self.setting("steal"))
            return
        self.crow.state = "fly"

    def _prey_pos(self, map) -> Vec2 | None:
        """Where what the crow is after lies (an apple's centre or a planted hedge's tile), or None once it is gone."""
        prey = self.prey
        if isinstance(prey, tuple):
            return map.tile_center(prey) if map.hand is not None and prey in map.hand.planted else None
        return prey.pos + Vec2(4, 4) if prey.alive else None

    def _feed(self, map) -> None:
        """At the end of its perch: the apple eaten, or the hedge pulled up (back to the hand)."""
        prey = self.prey
        if isinstance(prey, tuple):
            if map.hand is not None and prey in map.hand.planted:
                map.hand.uproot(prey)
                map.hand.left["hedge"] += 1
        elif prey is not None and prey.alive:
            prey.alive, prey.tally = False, False
        map.game.sm.effect("caw")

    def _mark(self, map, snake) -> None:
        """A swoop: from where it is to where the tail will be when it gets there."""
        crow, fps = self.crow, map.game.cfg.fps
        start = crow.center
        frames = int(self.setting("warn") * fps + (snake.segs[-1].pos - start).length() / self.DIVE)
        index = max(len(snake) // 2, len(snake) - 1 - frames)
        end = snake.segs[min(index, len(snake) - 1)].pos
        crow.state, crow.line, self.left = "warn", (start, end), self.setting("warn")
        map.game.sm.effect("caw")

    def _dive(self, map, snake, speed: float) -> None:
        """One frame of a swoop along its line: a hedge of the hand's on the way stuns it, at the end it cuts `chunk`
        off whatever of the snake lies there, then takes off again."""
        crow = self.crow
        start, end = crow.line
        arrived = self._fly(end, self.DIVE * speed)
        center = crow.center
        hand = map.hand
        tile = map.tile_xy(center)
        if hand is not None and (tile in hand.planted or tile in hand.sprouts):  # into the hand's hedge: stunned
            back = start - end
            if back.length() > 0:
                crow.pos = crow.pos + back * (6 / back.length())
            crow.state, crow.line, self.left = "stunned", None, self.setting("stun")
            map.game.sm.effect("boom")
            return
        if not arrived:
            return
        if snake.segment_at(center, self.STRIKE - snake.size) is not None:
            map.game.sm.effect("hurt")
            if not snake.cut(round(self.setting("chunk"))):
                map.snake_killed = True
        self._take_off(map, self.setting("swoop"))

    def _call(self, map, snake, seconds) -> None:
        """Every `call` seconds call a jackdaw, awake, while fewer than `flock` are about."""
        self.call_left -= seconds
        if self.call_left > 0:
            return
        self.call_left = self.setting("call")
        self.flock = [bird for bird in self.flock if bird.alive]
        if len(self.flock) < round(self.setting("flock")):
            bird = self._jackdaw.at_pos(map.new_pos(snake=snake, away=96))
            bird.asleep = False
            self.flock.append(bird)
            map.entities.append(bird)

    def bar(self, map, snake):
        return max(self.crow.health, 0) / self.full

    def phase_message(self):
        return "THE CROW STOOPS" if self.phase == 1 else "THE SKY GOES BLACK"

    def defeated(self, map):
        return not self.crow.alive

    def target(self):
        """The Crow while it is on the ground: the only time it can be bitten."""
        return self.crow.center if self.crow.alive and self.crow.grounded else None

    def swoop_line(self) -> "tuple[Vec2, Vec2] | None":
        """The line of a swoop it is warning of (for the bot playing the hand)."""
        return self.crow.line if self.crow.alive and self.crow.state == "warn" else None

    def danger(self):
        """Circles along a swoop's line while it warns and dives."""
        if not self.crow.alive or self.crow.state not in ("warn", "dive") or self.crow.line is None:
            return None
        start, end = self.crow.line
        steps = max(int((end - start).length() // 12), 1)
        return [(start + (end - start) * (i / steps), self.DANGER) for i in range(steps + 1)]


BOSSES: dict[str, type[Boss]] = {
    cls.key: cls
    for cls in [Hunger, AlphaBoss, CoreBoss, OuroborosBoss, BroodMotherBoss, MothershipBoss, ClockworkBoss, CrowBoss]
}


def load_boss(cfg, map: "Map") -> Boss:
    """The boss named by `cfg.type`, built from the level's `boss` section; raises on an unknown type."""
    if cfg.type not in BOSSES:
        raise ValueError(f"unknown boss type {cfg.type!r}, expected one of {sorted(BOSSES)}")
    return BOSSES[cfg.type](cfg, map)
