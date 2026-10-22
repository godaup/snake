"""The snake: its segments, how it moves, grows, turns and gets hurt."""

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
NECK = 3.0  # px along the body from the head that it can't bite: 3 segments at any normal speed, more while
# slowed (webs), when the segments lie closer


class SnakeSeg:
    """One round piece of the snake at `pos`: `size` is its radius, `col` its colour. Segment 0 is the head."""

    def __init__(self, pos: Vec2, size: int, col: int):
        self.pos = pos
        self.size = size
        self.col = col
        self.key: int | None = None  # the colour of a key it carries (the Workshop, see workshop.Key)

    def draw(self, offset: Vec2):
        """Draw the segment (one carrying a key bigger, in the key's colour), shifted by the camera's `offset`."""
        if self.key is not None:  # a key: bigger, in its colour
            from snake_quest.workshop import KEY_COLS

            pyxel.circ(self.pos.x + offset.x, self.pos.y + offset.y, self.size + 1, KEY_COLS[self.key])
            pyxel.pset(self.pos.x + offset.x, self.pos.y + offset.y, 7)
            return
        pyxel.circ(self.pos.x + offset.x, self.pos.y + offset.y, self.size, self.col)


class Snake:
    """The snake: a list of segments, the head first. Each frame the head moves `effective_speed` px along `heading`
    (where its `controller` steers it, see controls.py) and every other segment takes the place of the one ahead of
    it; `grow` adds segments at the tail one at a time (or cuts them while negative)."""

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
        self.mirrored: bool = False  # steering swapped (mirrored floor under the head), set by the map
        self.stalled: bool = False  # standing at a crate that can't move this frame (the Workshop)
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
        """The first segment, the one that moves and collides."""
        return self.segs[0]

    @property
    def speed(self):
        """The base speed in px per frame, kept within MIN_SPEED..MAX_SPEED (see `effective_speed` for boosts)."""
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
        """The colour of segment `index`: the palette's body colours repeated along the body."""
        return self.colors.body[index % len(self.colors.body)]

    def recolor(self, colors: Palette) -> None:
        """Switch palette, e.g. for the live preview in the customize screen."""
        self.colors = colors
        self.head.col = colors.head
        for index, seg in enumerate(self.segs[1:], start=1):
            seg.col = self.body_color(index)

    def turn(self, val: int):
        """Turn where the snake points by `val` degrees."""
        self.orient = (self.orient + val) % 360

    def draw(self, offset: Vec2):
        """Draw every segment, shifted by the camera's `offset`."""
        for seg in self.segs:
            seg.draw(offset)

    def update(self, dt: datetime.timedelta, map: "Map"):
        """One frame: steer (through the controller, the other way on mirrored floor), drift on ice and with the
        planets' pull, move (or stall at a crate), grow or shrink one segment and let the weapon fire."""
        self.boost_left = max(self.boost_left - dt.total_seconds(), 0.0)
        # steer
        steering = self.controller.steer(self, map)
        self.turn(round((-steering if self.mirrored else steering) * self.turn_speed))
        self.heading = drift(self.heading, self.orient, self.grip)
        if getattr(map, "wells", None):  # planets pull the snake round: where it points and where it moves
            pull = map.pull(self.head.pos, self.heading)
            self.orient, self.heading = (self.orient + pull) % 360, (self.heading + pull) % 360
        # move
        step = Vec2(self.effective_speed * pyxel.cos(self.heading), self.effective_speed * pyxel.sin(self.heading))
        works = getattr(map, "works", None)
        if works is not None:  # the Workshop: belts carry the head, and a crate that can't move stops it (a stall)
            step = works.push(self, step + works.drift_at(self.head.pos))
            self.stalled = step is None
        previous = copy(self.segs[-1].pos)
        if not self.stalled:
            previous = None
            for ix, seg in enumerate(self.segs):
                new = self.head.pos + step if ix == 0 else previous
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

    def neck(self, length: float = NECK) -> int:
        """Index of the first segment at least `length` px along the body from the head (segments lie as far apart as
        the snake moved per frame when they were laid: closer while it was slowed)."""
        along = 0.0
        for index in range(1, len(self.segs)):
            along += (self.segs[index].pos - self.segs[index - 1].pos).length()
            if along >= length:
                return index
        return len(self.segs)

    def self_intersect(self) -> bool:
        """Whether the head touches its own body beyond the neck (biting itself is the end)."""
        if len(self) < 4:
            return False
        return any([(self.head.pos - other.pos).length() < self.size for other in self.segs[max(3, self.neck()) :]])

    def covers(self, point: Vec2) -> bool:
        """Whether `point` lies on any segment."""
        return any([(point - seg.pos).length() < self.size for seg in self.segs])

    def get_collision_points(self) -> tuple[Vec2, Vec2]:
        """The two points of the head tested against walls (see `utils.collision_points`)."""
        return collision_points(self.head.pos, self.heading, self.size)
