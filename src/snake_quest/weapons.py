"""Weapons and their projectiles. The snake carries at most one weapon (`snake.weapon`, from a pickup such as
`GunPickup`), and its controller's `fire()` shoots it. The snake's shots only hit hostile entities, never the snake or
pickups; hostile shots (from turrets) only hit the snake."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import pyxel

from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake


class Projectile:
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

    def update(self, map: "Map", seconds: float, snake: "Snake | None" = None) -> None:
        """Fly on; gone after its lifetime, outside the map, at a wall (after its bounces) or after a hit: the snake's
        shots hit hostile entities, hostile shots the snake (cutting it where they strike, see `Snake.wound`)."""
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
        for ent in map.entities:
            if ent.alive and ent.hostile and ent.covers(self.pos):
                ent.hit(self.dmg)
                map.game.sm.effect("hurt")
                self.alive = False
                return

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
        pyxel.circ(self.pos.x + offset.x, self.pos.y + offset.y, self.size, self.col)


class Weapon(ABC):
    """Fires its pattern of projectiles when the controller says so, if it has ammo and its COOLDOWN is over."""

    name: ClassVar[str]  # upper case, shown in the HUD
    COOLDOWN: ClassVar[float]  # seconds between shots

    def __init__(self, ammo: int):
        self.ammo = ammo
        self.cooldown = 0.0

    @property
    def ready(self) -> bool:
        return self.ammo > 0 and self.cooldown <= 0

    def update(self, snake: "Snake", map: "Map", fire: bool, seconds: float) -> None:
        self.cooldown = max(self.cooldown - seconds, 0.0)
        if fire and self.ready:
            map.projectiles.extend(self.shots(snake))
            self.ammo -= 1
            self.cooldown = self.COOLDOWN
            map.game.sm.effect("shoot")

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
