import datetime
from abc import abstractmethod
from copy import copy
from typing import TYPE_CHECKING

import pyxel

from snake_quest.palettes import DEFAULT_PALETTE, Palette, palette
from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.map import Map

MAX_SPEED = 4
MIN_SPEED = 1
INIT_SPEED = 1.3
SPAWN_DELAY = datetime.timedelta(microseconds=300)


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

    def __init__(self, pos: Vec2, orient: int, size: int, colors: Palette | None = None):
        self.size: int = size
        self.orient: int = orient
        self._speed: float = INIT_SPEED
        self.boost_factor: float = 1.0  # temporary speed factor, see boost()
        self.boost_left: float = 0.0  # seconds
        self.colors: Palette = colors or palette(DEFAULT_PALETTE)
        self.segs: list[SnakeSeg] = [SnakeSeg(pos, self.size, self.colors.head)]
        self.grow: int = 20
        self.delay = datetime.timedelta(seconds=0)
        self.weapon: Weapon | None = None

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
        # move
        previous = None
        for ix, seg in enumerate(self.segs):
            if ix == 0:
                new = Vec2(
                    x=self.head.pos.x + (self.effective_speed * (pyxel.cos(self.orient))),
                    y=self.head.pos.y + (self.effective_speed * (pyxel.sin(self.orient))),
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
            print("A")
            self.weapon.update(map=map)

    def self_intersect(self) -> bool:
        if len(self) < 4:
            return False
        return any([(self.head.pos - other.pos).length() < self.size for other in self.segs[3:]])

    def covers(self, point: Vec2) -> bool:
        return any([(point - seg.pos).length() < self.size for seg in self.segs])

    def head_in_box(self, x, y, h, w) -> bool:
        if x <= self.head.pos.x <= x + w:
            return not (self.head.pos.y + self.size < y or self.head.pos.y - self.size > y + h)
        elif y <= self.head.pos.y <= y + h:
            return not (self.head.pos.x + self.size < x or self.head.pos.x - self.size > x + w)
        else:
            # check all 4 corners
            for vec in [Vec2(x, y), Vec2(x + w, y), Vec2(x, y + h), Vec2(x + w, y + h)]:
                if (self.head.pos - vec).length() < self.size:
                    return True
        return False

    def get_collision_points(self) -> tuple[Vec2, Vec2]:
        # horizontal extreme
        hor = Vec2(x=self.head.pos.x + pyxel.cos(self.orient) * (self.size + 0), y=self.head.pos.y)
        # vertical extreme
        ver = Vec2(x=self.head.pos.x, y=self.head.pos.y + pyxel.sin(self.orient) * (self.size + 0))
        return hor, ver


class Projectile:
    def __init__(self, pos: Vec2, size: int, speed: float, orient: int, col: int, dmg: int = 1):
        self.pos = pos
        self.size = size
        self.speed = speed
        self.dir = Vec2(x=pyxel.cos(orient), y=pyxel.sin(orient))
        self.col = col
        self.alive = True
        self.dmg = dmg

    def draw(self, offset: Vec2):
        pyxel.circ(self.pos.x + offset.x, self.pos.y + offset.y, self.size, self.col)

    def update(self, map: "Map", snake: "Snake"):
        # move
        self.pos = self.pos + self.dir * self.speed
        # check wall
        if map.check_on_wall(self.pos + self.dir * self.size):
            self.alive = False
        # check entities
        for ent in map.entities:
            if ent.covers(self.pos):
                ent.hit(self.dmg)
        # check snake
        hit_pattern = [(self.pos - seg.pos).length() < snake.size + self.size for seg in snake.segs]
        if any(hit_pattern):
            # find first hit
            hit_index = hit_pattern.index(True)
            snake.segs = snake.segs[: hit_index - 1]


class Weapon:
    def __init__(self, snake: Snake, delay: datetime.timedelta = datetime.timedelta(seconds=0.75)):
        self.snake = snake
        self.delay = delay
        self._last_time = datetime.datetime.now()

    def update(self, map: "Map"):
        if pyxel.btnp(pyxel.KEY_SPACE) and datetime.datetime.now() - self._last_time > self.delay:
            self._last_time = datetime.datetime.now()
            projectiles = self.next_pattern()
            map.projectiles.extend(projectiles)

    @abstractmethod
    def next_pattern(self) -> list[Projectile]:
        pass


class Gun(Weapon):
    def __init__(self, snake: "Snake"):
        super().__init__(snake=snake, delay=datetime.timedelta(seconds=1.5))

    def next_pattern(self) -> list[Projectile]:
        shot = Projectile(pos=self.snake.head.pos, size=2, speed=5.0, orient=self.snake.orient, col=9, dmg=1)
        return [shot]
