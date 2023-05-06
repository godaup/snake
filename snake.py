import datetime
from copy import copy
from dataclasses import dataclass

import pyxel

COL_BODY = 11
COL_HEAD = 7

SPAWN_DELAY = datetime.timedelta(microseconds=300)


@dataclass
class Vec2:
    """A simple 2D vector"""
    x: float = 0
    y: float = 0

    def __add__(self, other):
        if not isinstance(other, Vec2):
            raise ValueError
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, other):
        if not (isinstance(other, int) or isinstance(other, float)):
            raise ValueError
        return Vec2(other * self.x, other * self.y)

    def length(self):
        return pyxel.sqrt(self.x ** 2 + self.y ** 2)


class SnakeSeg:
    """Snake segment class"""

    def __init__(self, pos: Vec2, size: int, col: int):
        self.pos = pos
        self.size = size
        self.col = col

    def draw(self):
        pyxel.circ(self.pos.x, self.pos.y, self.size, self.col)


class Snake:
    """Snake class."""

    def __init__(self, pos: Vec2, orient: int, speed: float, size: int):
        self.size: int = size
        self.orient: int = orient
        self.speed: float = speed
        self.segs: list[SnakeSeg] = [SnakeSeg(pos, self.size, COL_HEAD)]  #
        self.grow: int = 200
        self.delay = datetime.timedelta(seconds=0)

    def __len__(self):
        return len(self.segs)

    @property
    def head(self) -> SnakeSeg:
        return self.segs[0]

    def turn(self, val: int):
        self.orient = (self.orient + val) % 360

    def draw(self):
        for seg in self.segs:
            seg.draw()

    def update(self, dt: datetime.timedelta):
        previous = None
        for ix, seg in enumerate(self.segs):
            if ix == 0:
                new = Vec2(x=self.head.pos.x + (self.speed * (pyxel.cos(self.orient))),
                           y=self.head.pos.y + (self.speed * (pyxel.sin(self.orient))))
            else:
                new = previous
            previous = copy(seg.pos)
            seg.pos = new

        if self.grow > 0:
            if self.delay < SPAWN_DELAY:
                self.delay += dt
            else:
                self.segs.append(SnakeSeg(pos=previous, size=self.size, col=COL_BODY))
                self.grow -= 1
                self.delay = datetime.timedelta(seconds=0)

    def self_intersect(self) -> bool:
        if len(self) < 4:
            return False
        return any([(self.head.pos - other.pos).length() < self.size for other in self.segs[3:]])

    def head_in_box(self, x, y, h, w) -> bool:
        if x <= self.head.pos.x <= x + w:
            return not (self.head.pos.y + self.size < y or self.head.pos.y - self.size > y + h)
        elif y <= self.head.pos.y <= y + h:
            return not (self.head.pos.x + self.size < x or self.head.pos.x - self.size > x + w)
        else:
            # check all 4 corners
            for vec in [Vec2(x, y), Vec2(x+w, y), Vec2(x, y+h), Vec2(x+w, y+h)]:
                if (self.head.pos - vec).length() < self.size:
                    return True
        return False
