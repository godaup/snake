"""The entities of arc 6, Space (registered like those in entity.py, which imports this module at its end)."""

from typing import TYPE_CHECKING

import pyxel

from snake_quest.entity import Drone, Entity, Turret, WeaponPickup, register
from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake


@register("tank")
class AirTank(Entity):
    """An air tank: refills the suit (the `oxygen` goal's `tank` share) and is worth POINTS. Timers bring new ones."""

    _img_x = 0
    _img_y = 17
    light = 14
    pullable = True
    POINTS = 1

    def on_intersect(self, snake: "Snake", map: "Map"):
        from snake_quest.goals import OxygenGoal  # goals import entities

        for goal in map.goals:
            if isinstance(goal, OxygenGoal):
                goal.refill()
        map.game.score += self.POINTS
        map.game.sm.effect("pickup")
        self.alive = False


@register("tractor")
class TractorPickup(WeaponPickup):
    _img_x = 2
    _img_y = 17
    AMMO = 12
    WEAPON = "Tractor"


@register("star")
class Star(Entity):
    """A star to collect (`collect_all: star`): POINTS points and LENGTH segments, gone for good once eaten."""

    _img_x = 1
    _img_y = 17
    light = 16
    pullable = True
    POINTS = 2
    LENGTH = 2

    def on_intersect(self, snake: "Snake", map: "Map"):
        snake.grow += self.LENGTH
        map.game.score += self.POINTS
        map.game.sm.effect("golden")
        self.alive = False


@register("planet")
class Planet(Entity):
    """A planet: it pulls the heading of whatever flies near it (see `Map.pull`): MASS / distance² degrees per frame
    (times the level's `gravity`), at most MAX_PULL, within REACH px. Its surface (RADIUS px) is a crash. Shots fly past
    it. Its mass is chosen at random between the bounds of MASS, so the wells differ."""

    _img_x = 10  # 2x2 sprite tiles from here
    _img_y = 17
    hostile = True
    avoid = False  # bots don't keep a hunter's distance, only clear of its surface:
    solid = True
    exposed = False
    tally = False
    MASS = (1000.0, 2200.0)  # px² degrees per frame
    MAX_PULL = 4.0  # degrees per frame
    REACH = 120  # px
    RADIUS = 7.5  # px
    COL_FIELD = 5

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.w = self.h = 16
        self.mass = pyxel.rndf(*self.MASS)

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(self.w / 2, self.h / 2)

    def covers(self, point: "Vec2") -> bool:
        return (point - self.center).length() <= self.RADIUS

    def pull(self, pos: "Vec2", heading: float, gravity: float) -> float:
        """Degrees this planet turns a heading at `pos` by, this frame (towards it)."""
        to_planet = self.center - pos
        distance = to_planet.length()
        if not 0 < distance < self.REACH:
            return 0.0
        strength = min(self.MAX_PULL, self.mass * gravity / (distance * distance))
        turn = (pyxel.atan2(to_planet.y, to_planet.x) - heading + 180) % 360 - 180
        return max(-strength, min(strength, turn))

    def on_intersect(self, snake: "Snake", map: "Map"):
        map.snake_killed = True  # burnt up

    def draw(self, offset: "Vec2"):
        centre = self.center + offset
        pyxel.dither(0.25)  # where the pull is strong (a degree per frame and more)
        pyxel.circb(centre.x, centre.y, (self.mass) ** 0.5, self.COL_FIELD)
        pyxel.dither(1.0)
        super().draw(offset)


@register("asteroid")
class Asteroid(Entity):
    """A rock adrift (Asteroids, level 29): it flies straight on and bounces off walls. Large (32 px), medium (16) or
    small (8): HEALTH shots break it into two of the next size down, flying apart at SPLIT degrees and faster; a small
    one is destroyed. Every piece counts for `destroy_all: asteroid`. Its touch is the end for the head; it cuts the
    body where it strikes and bounces off. A small one only stings STING segments off the tail, wherever it hits."""

    _img_x = 6  # the large one; the others are at SPRITES
    _img_y = 17
    hostile = True
    SIZES = {3: 32, 2: 16, 1: 8}  # size -> px
    SPRITES = {3: (6, 17), 2: (4, 17), 1: (3, 17)}
    HEALTH = {3: 3, 2: 2, 1: 1}
    SPEED = {3: 0.5, 2: 0.8, 1: 1.2}  # px per frame, scaled with the difficulty's speed
    SPLIT = 40  # degrees
    STING = 2
    COOL = 1.0  # seconds after a hit on the snake before it can hit again

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = "drift"  # always moving (bots aim at it at any range)
        self.heading = pyxel.rndf(0, 360)
        self.cool = 0.0
        self.resize(3)

    def resize(self, size: int) -> None:
        self.size = size
        self.w = self.h = self.SIZES[size]
        self.img_x, self.img_y = (8 * v for v in self.SPRITES[size])
        self.health = self.HEALTH[size]

    @property
    def avoid(self) -> bool:  # small ones only sting: bots don't swerve for them
        return self.size > 1

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(self.w / 2, self.h / 2)

    @property
    def radius(self) -> float:
        return self.w * 0.42

    def covers(self, point: "Vec2") -> bool:
        return (point - self.center).length() <= self.radius

    def update(self, snake: "Snake", map: "Map"):
        self.cool = max(0.0, self.cool - map.game.dt.total_seconds())
        speed = self.SPEED[self.size] * map.game.difficulty.speed
        step = Vec2(pyxel.cos(self.heading), pyxel.sin(self.heading)) * speed
        edge = self.radius
        ahead_x = self.center + Vec2(edge if step.x > 0 else -edge, 0) + Vec2(step.x, 0)
        ahead_y = self.center + Vec2(0, edge if step.y > 0 else -edge) + Vec2(0, step.y)
        if map.check_on_wall(ahead_x):  # bounce off the side it runs into
            step = Vec2(-step.x, step.y)
        if map.check_on_wall(ahead_y):
            step = Vec2(step.x, -step.y)
        self.heading = pyxel.atan2(step.y, step.x)
        self.pos = self.pos + step
        if self.cool <= 0:
            index = next((i for i, seg in enumerate(snake.segs) if (seg.pos - self.center).length() < edge + 2), None)
            if index is not None:
                self.strike(snake, map, index)

    def strike(self, snake: "Snake", map: "Map", index: int) -> None:
        map.game.sm.effect("hurt")
        self.cool = self.COOL
        away = self.center - snake.segs[index].pos
        self.heading = pyxel.atan2(away.y, away.x)
        if self.size == 1:  # a pebble only stings, even the head
            if not snake.cut(self.STING):
                map.snake_killed = True
        elif index == 0 or not snake.wound(index):
            map.snake_killed = True

    def on_intersect(self, snake: "Snake", map: "Map"):
        if self.cool <= 0:
            self.strike(snake, map, 0)

    def hit(self, dmg: int):
        self.health -= dmg
        if self.health > 0:
            return
        self.alive, self.killed = False, True
        self.pieces = []
        if self.size > 1:
            for turn in (-self.SPLIT, self.SPLIT):
                piece = Asteroid.at_pos(Vec2(self.pos.x, self.pos.y))
                piece.resize(self.size - 1)
                piece.pos = self.center - Vec2(piece.w / 2, piece.h / 2)
                piece.heading = (self.heading + turn) % 360
                self.pieces.append(piece)


@register("raider")
class Raider(Drone):
    """A raider of the Mothership's: a drone (it flies over everything at the head and stings) that also fires a slow
    hostile shot every RELOAD seconds when the head is within RANGE px ahead of it."""

    _img_x = 12
    _img_y = 17
    SPEED = 1.4
    TURN = 4
    RELOAD = 2.5
    RANGE = 110
    SHOT_SPEED = 2.0
    AIM = 15  # degrees

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.left = self.RELOAD

    def update(self, snake: "Snake", map: "Map"):
        from snake_quest.weapons import Projectile  # weapons need nothing from here

        super().update(snake, map)
        self.left -= map.game.dt.total_seconds()
        to_head = snake.head.pos - self.center
        ahead = abs((pyxel.atan2(to_head.y, to_head.x) - self.heading + 180) % 360 - 180) < self.AIM
        if self.alive and self.left <= 0 and ahead and to_head.length() < self.RANGE:
            self.left = self.RELOAD * map.game.difficulty.hostile
            speed = self.SHOT_SPEED * map.game.difficulty.speed
            lifetime = self.RANGE / speed / map.game.cfg.fps
            map.projectiles.append(Projectile(self.center, self.heading, speed, 1, 8, hostile=True, lifetime=lifetime))


@register("pod")
class EnginePod(Turret):
    """An engine pod of the Mothership: a turret riding on its hull (the boss moves it), HEALTH shots."""

    _img_x = 13
    _img_y = 17
    HOT_IMG_X = 13  # no eye: it flashes instead
    HEALTH = 2
    RANGE = 100  # px: shorter than a gun's, so careful aim from afar is safe


@register("mothership")
class Mothership(Entity):
    """The Mothership (level 30, put in and flown by the `mothership` boss): a 32x16 ship. Shielded while its engine
    pods stand (shots glint off); with its bay open (`open`), shots hurt it. Its hull is the end for the head. In the
    last phase its tractor beam pulls (`pull`, like a planet's: Map.pull asks it too)."""

    _img_x = 0  # 4x2 sprite tiles from here
    _img_y = 19
    hostile = True
    avoid = False  # it moves through the level on its course: bots keep out of its way (the boss's danger)
    tally = False
    FLASH = 0.15
    COL_SHIELD, COL_GLINT, COL_BEAM = 12, 7, 12

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.w, self.h = 32, 16
        self.health = 12
        self.shielded = True
        self.open = False  # the bay
        self.tractor = 0.0  # its beam's strength (px² degrees per frame), 0 while off
        self.reach = 140  # px
        self.flash = 0.0

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(self.w / 2, self.h / 2)

    @property
    def exposed(self) -> bool:
        return self.open or self.shielded  # shots meet the shield (and glint) or the open bay

    @property
    def armored(self) -> bool:  # the shield: every shot glances off
        return self.shielded

    def covers(self, point: "Vec2") -> bool:
        d = point - self.center
        return (d.x / (self.w / 2)) ** 2 + (d.y / (self.h / 2)) ** 2 <= 1.0

    def deflect(self):
        self.flash = self.FLASH

    def hit(self, dmg: int):
        if self.open and not self.shielded:
            super().hit(dmg)
            self.flash = self.FLASH

    def pull(self, pos: "Vec2", heading: float, gravity: float) -> float:
        if not self.tractor:
            return 0.0
        to_ship = self.center - pos
        distance = to_ship.length()
        if not 0 < distance < self.reach:
            return 0.0
        strength = min(3.0, self.tractor / (distance * distance))
        turn = (pyxel.atan2(to_ship.y, to_ship.x) - heading + 180) % 360 - 180
        return max(-strength, min(strength, turn))

    def update(self, snake: "Snake", map: "Map"):
        self.flash = max(self.flash - map.game.dt.total_seconds(), 0.0)

    def on_intersect(self, snake: "Snake", map: "Map"):
        map.snake_killed = True

    def draw(self, offset: "Vec2"):
        centre = self.center + offset
        if self.tractor and pyxel.frame_count % 3 == 0:
            pyxel.dither(0.25)
            pyxel.circb(centre.x, centre.y, self.reach * 0.4, self.COL_BEAM)
            pyxel.dither(1.0)
        if not (self.flash > 0 and not self.shielded and pyxel.frame_count % 2):
            super().draw(offset)
        if self.open:
            pyxel.rect(centre.x - 3, centre.y - 2, 6, 4, 10 if pyxel.frame_count % 6 < 3 else 9)
        if self.shielded:
            pyxel.dither(0.5 if pyxel.frame_count % 8 < 4 else 0.75)
            col = self.COL_GLINT if self.flash > 0 else self.COL_SHIELD
            pyxel.ellib(centre.x - 19, centre.y - 11, 38, 22, col)
            pyxel.dither(1.0)
