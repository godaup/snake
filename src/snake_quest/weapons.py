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

    def update(self, map: "Map", seconds: float, snake: "Snake | None" = None) -> None:
        """Fly on; gone after its lifetime, at a wall, outside the map or after a hit: the snake's shots hit hostile
        entities, hostile shots the snake (cutting it where they strike, see `Snake.wound`)."""
        self.pos = self.pos + self.dir * self.speed
        self.age += seconds
        outside = not (0 <= self.pos.x < map.cfg.width and map.header <= self.pos.y < map.header + map.cfg.height)
        if self.age >= self.lifetime or outside or map.check_on_wall(self.pos):
            self.alive = False
            return
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

    @property
    def range(self) -> float:
        """How far a shot flies, in px (24 frames per second)."""
        return self.SPEED * 24 * Projectile.LIFETIME
