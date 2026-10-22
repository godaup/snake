"""Weapons and their projectiles. The snake carries at most one weapon (`snake.weapon`, from a pickup such as
`GunPickup`), and its controller's `fire()` shoots it. The snake's shots only hit hostile entities, never the snake or
pickups; hostile shots (from turrets) only hit the snake. Armoured entities (`armored`) only take piercing shots (the
Laser); other shots glance off them."""

import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import pyxel

from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake

STEP = 4  # px: a shot tests for hits at least this often along its flight


class Projectile:
    """A shot flying straight (or homing, or bouncing) at `speed` px per frame; the snake's hit hostile entities,
    hostile ones the snake."""

    LIFETIME = 1.2  # seconds before it fizzles out

    def __init__(
        self,
        pos: Vec2,
        orient: float,
        speed: float,
        size: int,
        col: int,
        dmg: int = 1,
        hostile: bool = False,
        lifetime: float | None = None,
        bounces: int = 0,
        pierce: bool = False,
        homing: float = 0,
    ):
        self.pos = pos
        self.dir = Vec2(x=pyxel.cos(orient), y=pyxel.sin(orient))
        self.speed = speed  # px per frame
        self.size = size
        self.col = col
        self.dmg = dmg
        self.age = 0.0
        self.alive = True
        self.hostile = hostile  # fired at the snake: hits it, never an entity
        self.lifetime = self.LIFETIME if lifetime is None else lifetime  # seconds before it fizzles out
        self.bounces = bounces  # walls it bounces off before one stops it
        self.pierce = pierce  # through armour, and on through every entity it hits (each once)
        self.struck: list = []  # what a piercing shot has hit
        self.homing = homing  # degrees per frame it turns towards the nearest hostile entity within HOMING_RANGE

    def update(self, map: "Map", seconds: float, snake: "Snake | None" = None) -> None:
        """Fly on; gone after its lifetime, outside the map, at a wall (after its bounces) or after a hit: the snake's
        shots hit hostile entities, hostile shots the snake (cutting it where they strike, see `Snake.wound`)."""
        if self.homing and not self.hostile:
            self._home(map)
        before, self.pos = self.pos, self.pos + self.dir * self.speed
        self.age += seconds
        outside = not (0 <= self.pos.x < map.cfg.width and map.header <= self.pos.y < map.header + map.cfg.height)
        if self.age >= self.lifetime or outside or (map.check_on_wall(self.pos) and self.bounces <= 0):
            self.alive = False
            return
        if map.check_on_wall(self.pos):
            self._bounce(map, before)
        if self.hostile:
            index = snake.segment_at(self.pos, self.size) if snake is not None else None
            if index is not None:
                map.game.sm.effect("hurt")
                if not snake.wound(index):
                    map.snake_killed = True
                self.alive = False
            return
        # fast shots (the Laser) fly farther per frame than an entity is wide: test the way between, too
        steps = max(1, math.ceil(self.speed / STEP))
        points = [before + (self.pos - before) * (i / steps) for i in range(1, steps + 1)]
        for ent in map.entities:
            hits = ent.alive and ent.hostile and ent.exposed and ent not in self.struck
            hits = hits and any(ent.covers(p) for p in points)
            if hits:
                if ent.armored and not self.pierce:
                    ent.deflect()
                    self.alive = False
                    return
                ent.hit(self.dmg)
                map.game.sm.effect("hurt")
                if not self.pierce:
                    self.alive = False
                    return
                self.struck.append(ent)

    HOMING_RANGE = 120  # px

    def _home(self, map: "Map") -> None:
        """Turn at most `homing` degrees towards the nearest hostile entity within HOMING_RANGE that it can hurt."""
        best, target = self.HOMING_RANGE, None
        for ent in map.entities:
            if not (ent.alive and ent.hostile and ent.exposed) or (ent.armored and not self.pierce):
                continue
            to_ent = ent.pos + Vec2(ent.w / 2, ent.h / 2) - self.pos
            if to_ent.length() < best:
                best, target = to_ent.length(), to_ent
        if target is None:
            return
        heading = pyxel.atan2(self.dir.y, self.dir.x)
        turn = (pyxel.atan2(target.y, target.x) - heading + 180) % 360 - 180
        heading += max(-self.homing, min(self.homing, turn))
        self.dir = Vec2(pyxel.cos(heading), pyxel.sin(heading))

    def _bounce(self, map: "Map", before: Vec2) -> None:
        """Back to where it was before flying into the wall, turned around along the wall's side it hit (both ways in a
        corner)."""
        step = self.dir * self.speed
        flip_x = map.check_on_wall(Vec2(before.x + step.x, before.y))
        flip_y = map.check_on_wall(Vec2(before.x, before.y + step.y))
        if not (flip_x or flip_y):
            flip_x = flip_y = True
        self.dir = Vec2(-self.dir.x if flip_x else self.dir.x, -self.dir.y if flip_y else self.dir.y)
        self.pos = before
        self.bounces -= 1

    def draw(self, offset: Vec2) -> None:
        """A dot, or for a beam a streak along its flight."""
        if self.pierce:  # a beam: a streak along its flight
            tail = self.pos - self.dir * (self.speed * 2)
            pyxel.line(tail.x + offset.x, tail.y + offset.y, self.pos.x + offset.x, self.pos.y + offset.y, self.col)
            return
        pyxel.circ(self.pos.x + offset.x, self.pos.y + offset.y, self.size, self.col)


class Weapon(ABC):
    """Fires its pattern of projectiles when the controller says so, if it has ammo and its COOLDOWN is over."""

    name: ClassVar[str]  # upper case, shown in the HUD
    COOLDOWN: ClassVar[float]  # seconds between shots
    COL: ClassVar[int] = 7  # its shots' colour, and the ammo band's on the snake (see Snake.draw)

    def __init__(self, ammo: int, hostile: bool = False):
        self.ammo = ammo
        self.cooldown = 0.0
        self.hostile = hostile  # carried by a rival: its shots hit the player's snake

    @property
    def ready(self) -> bool:
        """Whether it can fire: ammo left and the cooldown over."""
        return self.ammo > 0 and self.cooldown <= 0

    def update(self, snake: "Snake", map: "Map", fire: bool, seconds: float) -> None:
        """One frame: cool down, and on `fire` while ready release a shot (or a mine), using up ammo."""
        self.cooldown = max(self.cooldown - seconds, 0.0)
        if fire and self.ready:
            self.release(snake, map)
            self.ammo -= 1
            self.cooldown = self.COOLDOWN
            map.game.sm.effect("shoot")

    def release(self, snake: "Snake", map: "Map") -> None:
        """One shot: its projectiles fly off from the head."""
        shots = self.shots(snake)
        for shot in shots:
            shot.hostile = self.hostile
        map.projectiles.extend(shots)

    @abstractmethod
    def shots(self, snake: "Snake") -> list[Projectile]:
        """The projectiles of one shot, starting at the snake's head."""


class Gun(Weapon):
    """A single straight shot."""

    name = "GUN"
    COOLDOWN = 0.4
    SPEED = 5.0  # px per frame
    COL = 10

    def shots(self, snake):
        start = snake.head.pos + Vec2(pyxel.cos(snake.orient), pyxel.sin(snake.orient)) * (snake.size + 1)
        return [Projectile(pos=start, orient=snake.orient, speed=self.SPEED, size=1, col=self.COL)]

    FAN = 0  # degrees between the shots of a fan (bots aim this much wider)
    LIFETIME = Projectile.LIFETIME

    @property
    def range(self) -> float:
        """How far a shot flies, in px (24 frames per second)."""
        return self.SPEED * 24 * self.LIFETIME


class Spread(Gun):
    """A fan of three shots, FAN degrees apart."""

    name = "SPREAD"
    COOLDOWN = 0.5
    COL = 9
    FAN = 14

    def shots(self, snake):
        start = snake.head.pos + Vec2(pyxel.cos(snake.orient), pyxel.sin(snake.orient)) * (snake.size + 1)
        return [
            Projectile(pos=start, orient=snake.orient + turn, speed=self.SPEED, size=1, col=self.COL)
            for turn in (-self.FAN, 0, self.FAN)
        ]


class Ricochet(Gun):
    """A shot that bounces off up to BOUNCES walls and flies longer: around corners, at what hides behind them."""

    name = "RICOCHET"
    COL = 12
    BOUNCES = 3
    LIFETIME = 2.0

    def shots(self, snake):
        start = snake.head.pos + Vec2(pyxel.cos(snake.orient), pyxel.sin(snake.orient)) * (snake.size + 1)
        return [
            Projectile(
                pos=start,
                orient=snake.orient,
                speed=self.SPEED,
                size=1,
                col=self.COL,
                lifetime=self.LIFETIME,
                bounces=self.BOUNCES,
            )
        ]


class Laser(Gun):
    """A fast beam that pierces: through armour, and on through everything in its way. Short range."""

    name = "LASER"
    COOLDOWN = 0.5
    SPEED = 8.0
    COL = 8
    LIFETIME = 0.7
    PIERCE = True  # bots aim it at armoured entities too

    def shots(self, snake):
        start = snake.head.pos + Vec2(pyxel.cos(snake.orient), pyxel.sin(snake.orient)) * (snake.size + 1)
        return [
            Projectile(
                pos=start,
                orient=snake.orient,
                speed=self.SPEED,
                size=1,
                col=self.COL,
                lifetime=self.LIFETIME,
                pierce=self.PIERCE,
            )
        ]


class Homing(Gun):
    """A slower shot that steers towards the nearest enemy (TURN degrees per frame), so it needs only rough aim."""

    name = "HOMING"
    COOLDOWN = 0.5
    SPEED = 3.5
    COL = 11
    LIFETIME = 2.0
    TURN = 7
    FAN = 30  # bots fire when a target is this much off straight ahead: the shot finds it

    def shots(self, snake):
        start = snake.head.pos + Vec2(pyxel.cos(snake.orient), pyxel.sin(snake.orient)) * (snake.size + 1)
        return [
            Projectile(
                pos=start,
                orient=snake.orient,
                speed=self.SPEED,
                size=1,
                col=self.COL,
                lifetime=self.LIFETIME,
                homing=self.TURN,
            )
        ]


class FlareShot(Projectile):
    """A flare in flight: where it comes to rest (at the end of its flight, before a wall, or on what it hits) it burns
    on as a Burning light."""

    def update(self, map: "Map", seconds: float, snake: "Snake | None" = None) -> None:
        if not self.alive:  # burning already
            return
        before = self.pos
        super().update(map, seconds, snake)
        if not self.alive:
            from snake_quest.caves import Burning  # entities import weapons lazily too

            rest = before if map.check_on_wall(self.pos) else self.pos
            if not map.check_on_wall(rest):
                map.entities.append(Burning.at_pos(Vec2(rest.x - 4, rest.y - 4)))


class Flare(Gun):
    """A slow, short shot that burns on where it comes to rest (see FlareShot): a light in the dark that scares bats
    away and burns webs; it hurts what it hits, too."""

    name = "FLARE"
    COOLDOWN = 1.0
    SPEED = 3.0
    COL = 9
    LIFETIME = 0.8

    def shots(self, snake):
        start = snake.head.pos + Vec2(pyxel.cos(snake.orient), pyxel.sin(snake.orient)) * (snake.size + 1)
        return [
            FlareShot(pos=start, orient=snake.orient, speed=self.SPEED, size=1, col=self.COL, lifetime=self.LIFETIME)
        ]


class TractorBeam(Projectile):
    """The Tractor's pull, PULSE seconds long: every frame it draws the nearest pickup (`Entity.pullable`) within
    RANGE px and CONE degrees of where the head points towards the head, PULL px per frame. Drawn as a dotted beam."""

    RANGE = 80  # px
    CONE = 25  # degrees off straight ahead
    PULL = 2.0  # px per frame
    PULSE = 0.6  # seconds
    COL = 12

    def __init__(self, snake: "Snake"):
        super().__init__(pos=snake.head.pos, orient=snake.orient, speed=0, size=0, col=self.COL, lifetime=self.PULSE)
        self.snake = snake
        self.target = None

    @classmethod
    def in_cone(cls, snake: "Snake", ent) -> bool:
        """Whether `ent` lies within RANGE px of the head and CONE degrees of where it points."""
        to_ent = ent.pos + Vec2(ent.w / 2, ent.h / 2) - snake.head.pos
        if not 0 < to_ent.length() <= cls.RANGE:
            return False
        return abs((pyxel.atan2(to_ent.y, to_ent.x) - snake.orient + 180) % 360 - 180) <= cls.CONE

    def update(self, map: "Map", seconds: float, snake: "Snake | None" = None) -> None:
        self.age += seconds
        if self.age >= self.lifetime:
            self.alive = False
            return
        self.pos = self.snake.head.pos
        pulled = [ent for ent in map.entities if ent.alive and ent.pullable and self.in_cone(self.snake, ent)]
        self.target = min(pulled, key=lambda ent: (ent.pos - self.pos).length(), default=None)
        if self.target is not None:
            to_head = self.pos - (self.target.pos + Vec2(self.target.w / 2, self.target.h / 2))
            length = to_head.length()
            if length > 0:
                self.target.pos = self.target.pos + to_head * (min(self.PULL, length) / length)

    def draw(self, offset: Vec2) -> None:
        """A dotted, crawling line from the head to what it pulls."""
        if self.target is None:
            return
        end = self.target.pos + Vec2(self.target.w / 2, self.target.h / 2)
        steps = max(1, int((end - self.pos).length() // 3))
        for i in range((pyxel.frame_count // 2) % 2, steps, 2):
            point = self.pos + (end - self.pos) * (i / steps)
            pyxel.pset(point.x + offset.x, point.y + offset.y, self.COL)


class Tractor(Weapon):
    """Not a gun: every press sends out a TractorBeam that pulls the nearest pickup ahead in. Each pulse is a charge."""

    name = "TRACTOR"
    COOLDOWN = TractorBeam.PULSE
    COL = TractorBeam.COL
    PULLS = True  # bots fire it when a pickup is in its cone

    def release(self, snake, map):
        map.projectiles.append(TractorBeam(snake))

    def shots(self, snake):
        return []


class Mines(Weapon):
    """Drops a mine behind the tail (see the Mine entity), for whatever follows the snake's trail."""

    name = "MINES"
    COOLDOWN = 0.6
    COL = 13
    DROPS = True  # bots drop them when something is on the snake's trail, instead of aiming

    def release(self, snake, map):
        from snake_quest.entity import Mine  # entity imports this module lazily too

        tail = snake.segs[-1].pos
        map.entities.append(Mine.at_pos(Vec2(tail.x - 4, tail.y - 4)))

    def shots(self, snake):
        return []
