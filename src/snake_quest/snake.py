import datetime
from copy import copy
from typing import TYPE_CHECKING

import pyxel

from snake_quest.controls import Controller
from snake_quest.palettes import DEFAULT_PALETTE, Palette, palette
from snake_quest.utils import Vec2, collision_points, drift

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.weapons import Weapon

MAX_SPEED = 4
MIN_SPEED = 1
INIT_SPEED = 1.3
SPAWN_DELAY = datetime.timedelta(microseconds=300)
TURN_SPEED = 9  # degrees per frame at full steering


class SnakeSeg:
    """Snake segment class"""

    def __init__(self, pos: Vec2, size: int, col: int):
        self.pos = pos
        self.size = size
        self.col = col

    def draw(self, offset: Vec2):
        pyxel.circ(self.pos.x + offset.x, self.pos.y + offset.y, self.size, self.col)


class Snake:
    """Snake class."""

    def __init__(
        self,
        pos: Vec2,
        orient: int,
        size: int,
        colors: Palette | None = None,
        controller: Controller | None = None,
        turn_speed: int = TURN_SPEED,
        speed: float = INIT_SPEED,
    ):
        self.size: int = size
        self.orient: int = orient  # where it points (steering turns this)
        self.heading: float = orient  # where it moves: the same, except on ice (see drift)
        self.grip: float = 1.0  # set by the map from the ground under the head
        self._speed: float = speed
        self.boost_factor: float = 1.0  # temporary speed factor, see boost()
        self.boost_left: float = 0.0  # seconds
        self.colors: Palette = colors or palette(DEFAULT_PALETTE)
        self.segs: list[SnakeSeg] = [SnakeSeg(pos, self.size, self.colors.head)]
        self.grow: int = 20
        self.delay = datetime.timedelta(seconds=0)
        self.weapon: Weapon | None = None  # see weapons.py; picked up in the level
        self.controller: Controller = controller or Controller()  # the default one goes straight
        self.turn_speed = turn_speed

    def __len__(self):
        return len(self.segs)

    @property
    def head(self) -> SnakeSeg:
        return self.segs[0]

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, val):
        self._speed = max(min(val, MAX_SPEED), MIN_SPEED)

    @property
    def effective_speed(self) -> float:
        """Speed including an active boost, never above MAX_SPEED."""
        return min(self._speed * self.boost_factor, MAX_SPEED) if self.boost_left > 0 else self._speed

    def boost(self, factor: float, seconds: float) -> None:
        """Move `factor` times faster for `seconds`; a new boost replaces a running one."""
        self.boost_factor = factor
        self.boost_left = seconds

    def body_color(self, index: int) -> int:
        return self.colors.body[index % len(self.colors.body)]

    def recolor(self, colors: Palette) -> None:
        """Switch palette, e.g. for the live preview in the customize screen."""
        self.colors = colors
        self.head.col = colors.head
        for index, seg in enumerate(self.segs[1:], start=1):
            seg.col = self.body_color(index)

    def turn(self, val: int):
        self.orient = (self.orient + val) % 360

    def draw(self, offset: Vec2):
        for seg in self.segs:
            seg.draw(offset)

    def update(self, dt: datetime.timedelta, map: "Map"):
        self.boost_left = max(self.boost_left - dt.total_seconds(), 0.0)
        # steer
        self.turn(round(self.controller.steer(self, map) * self.turn_speed))
        self.heading = drift(self.heading, self.orient, self.grip)
        # move
        previous = None
        for ix, seg in enumerate(self.segs):
            if ix == 0:
                new = Vec2(
                    x=self.head.pos.x + (self.effective_speed * (pyxel.cos(self.heading))),
                    y=self.head.pos.y + (self.effective_speed * (pyxel.sin(self.heading))),
                )
            else:
                new = previous
            previous = copy(seg.pos)
            seg.pos = new
        # grow
        if self.grow > 0:
            if self.delay < SPAWN_DELAY:
                self.delay += dt
            else:
                self.segs.append(SnakeSeg(pos=previous, size=self.size, col=self.body_color(len(self))))
                self.grow -= 1
                self.delay = datetime.timedelta(seconds=0)
        # shrink
        if self.grow < 0:
            if len(self) < -1 * self.grow:
                raise RuntimeError("Dead")
            self.segs = self.segs[: self.grow]
        # fire
        if self.weapon:
            self.weapon.update(self, map, fire=self.controller.fire(self, map), seconds=dt.total_seconds())

    def cut(self, n: int) -> bool:
        """Lose `n` segments from the tail; False (and nothing cut) when the snake isn't longer than that."""
        if len(self) <= n:
            return False
        self.segs = self.segs[:-n]
        return True

    def segment_at(self, point: Vec2, radius: float = 0) -> int | None:
        """Index of the segment nearest the head that `point` touches (within the segment size plus `radius`)."""
        for index, seg in enumerate(self.segs):
            if (point - seg.pos).length() < self.size + radius:
                return index
        return None

    def wound(self, index: int) -> bool:
        """A shot hits segment `index`: the body from there to the tail falls off, but never more than half of it (a
        shot from the front, dodged at the last moment, still hits the body right behind the head); a hit on the head
        costs half. False (and nothing lost) when the snake is too short to lose half."""
        if index > 0:
            self.segs = self.segs[: max(index, len(self) // 2)]
            return True
        return len(self) >= 4 and self.cut(len(self) // 2)

    def self_intersect(self) -> bool:
        if len(self) < 4:
            return False
        return any([(self.head.pos - other.pos).length() < self.size for other in self.segs[3:]])

    def covers(self, point: Vec2) -> bool:
        return any([(point - seg.pos).length() < self.size for seg in self.segs])

    def get_collision_points(self) -> tuple[Vec2, Vec2]:
        return collision_points(self.head.pos, self.heading, self.size)
