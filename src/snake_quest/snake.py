"""The snake: its segments, how it moves, grows, turns and gets hurt."""

import datetime
import math
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
# its looks (drawing only: collisions use `size` everywhere)
TAPER = 6  # tail segments drawn thinner (radius 1, the last two a single pixel), on snakes longer than twice that
TONGUE_EVERY, TONGUE_OUT = 2.4, 0.3  # seconds: the tongue flicks out for TONGUE_OUT once every TONGUE_EVERY
BLINK_EVERY, BLINK = 3.7, 0.15  # seconds: the eyes shut for BLINK once every BLINK_EVERY
PIE_RADIUS, PIE_ABOVE, PIE_ASIDE, PIE_FOLLOW = 4, 14, 10, 0.3  # px; px over the head (or aside, clear of the body);
# share of the way it catches up per frame
PIE_KICK = 0.12  # seconds the ammo pie swells when a shot is fired (see _draw_ammo_pie)
PIE_CUTS = 8  # cut into pieces while it holds at most this many shots
PIE_LOW = 0.25  # share of the shots left below which it blinks
COL_TONGUE, COL_LID, COL_PIE_EMPTY = 8, 13, 1
DARK = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 1, 6: 5, 7: 13, 8: 2, 9: 4, 10: 9, 11: 3, 12: 5, 13: 5, 14: 2, 15: 4}
LIGHT = {0: 5, 1: 5, 2: 14, 3: 11, 4: 9, 5: 12, 6: 7, 7: 7, 8: 14, 9: 10, 10: 7, 11: 7, 12: 6, 13: 7, 14: 15, 15: 7}


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
        self.clock = 0.0  # seconds it has lived, for the tongue and the blinking (no random numbers: bots replay)
        self.pie: Vec2 | None = None  # where the ammo pie floats (see _draw_ammo_pie)
        self.ammo_full = 0  # the most shots the weapon carried has held: the whole pie
        self.pie_kick = 0.0  # seconds left of its swell after a shot
        self._carried: Weapon | None = None
        self._ammo_before = 0

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
        """Draw the snake shifted by the camera's `offset`: the body from the tail up (tapering to a point, the ammo
        and the gloss on top), then the head with its eyes and, now and then, its tongue, and the ammo pie over it."""
        n = len(self.segs)
        for index in range(n - 1, 0, -1):
            seg = self.segs[index]
            if seg.key is not None:
                seg.draw(offset)
                continue
            radius = self.size
            if n > 2 * TAPER and index >= n - TAPER:
                radius = 0 if index >= n - 2 else 1
            pyxel.circ(seg.pos.x + offset.x, seg.pos.y + offset.y, radius, seg.col)
        # the gloss along the back on top, as the segments overlap
        for index in range(1, n - TAPER if n > 2 * TAPER else n) if self.colors.gloss else ():
            seg = self.segs[index]
            if seg.key is not None:
                continue
            x, y = seg.pos.x + offset.x, seg.pos.y + offset.y
            ahead = self.segs[index - 1].pos - seg.pos
            length = ahead.length() or 1
            pyxel.pset(x + ahead.y / length * 1.2 - 0.3, y - ahead.x / length * 1.2 - 0.3, LIGHT[seg.col])
        self._draw_head(offset)
        if self.weapon is not None and self.pie is not None:
            self._draw_ammo_pie(offset)

    def _draw_ammo_pie(self, offset: Vec2) -> None:
        """The ammo as a pie over the head in the weapon's colour: a piece for each shot the weapon has held, the
        ones fired gone (dark), clockwise from the top, with a rim and a gloss. It swells a little at each shot and
        blinks when the shots run low."""
        weapon = self.weapon
        full, left = max(self.ammo_full, 1), weapon.ammo
        radius = PIE_RADIUS + (1 if self.pie_kick > 0 else 0)
        x, y = round(self.pie.x + offset.x), round(self.pie.y + offset.y + math.sin(self.clock * 4))
        col, rim = weapon.COL, DARK[weapon.COL]
        if left and left <= full * PIE_LOW and self.clock % 0.5 < 0.25:  # running low
            col = LIGHT[col]
        filled = 360 * left / full
        reach = radius * radius + radius
        for py in range(-radius, radius + 1):
            for px in range(-radius, radius + 1):
                if px * px + py * py > reach:
                    continue
                if math.degrees(math.atan2(px, -py)) % 360 < filled:
                    shine = px + py < -radius and px * px + py * py > radius  # the gloss, upper left
                    pyxel.pset(x + px, y + py, LIGHT[col] if shine else col)
                else:
                    pyxel.pset(x + px, y + py, COL_PIE_EMPTY)
        if full <= PIE_CUTS:
            for piece in range(full):
                angle = math.radians(piece * 360 / full)
                pyxel.line(x, y, x + math.sin(angle) * radius, y - math.cos(angle) * radius, rim)
        pyxel.circb(x, y, radius + 1, rim)

    def _draw_head(self, offset: Vec2) -> None:
        """A head one pixel bigger than the body, its eyes to either side of where it points (shut while it
        blinks), and the forked tongue while it flicks."""
        x, y = self.head.pos.x + offset.x, self.head.pos.y + offset.y
        dx, dy = pyxel.cos(self.orient), pyxel.sin(self.orient)
        radius = self.size + 1
        if self.clock % TONGUE_EVERY < TONGUE_OUT:
            tip_x, tip_y = x + dx * (radius + 4), y + dy * (radius + 4)
            pyxel.line(x + dx * (radius + 1), y + dy * (radius + 1), tip_x, tip_y, COL_TONGUE)
            for side in (-1, 1):
                pyxel.pset(tip_x + dx + dy * side, tip_y + dy - dx * side, COL_TONGUE)
        pyxel.circ(x, y, radius, self.head.col)
        if self.colors.gloss:
            pyxel.pset(x + dy * 1.5 - 0.5, y - dx * 1.5 - 0.5, LIGHT[self.head.col])
        eyes = COL_LID if self.clock % BLINK_EVERY < BLINK else self.colors.eyes
        for side in (-1, 1):
            pyxel.pset(x + dx * 1.2 + dy * side * 1.6, y + dy * 1.2 - dx * side * 1.6, eyes)

    def update(self, dt: datetime.timedelta, map: "Map"):
        """One frame: steer (through the controller, the other way on mirrored floor), drift on ice and with the
        planets' pull, move (or stall at a crate), grow or shrink one segment and let the weapon fire."""
        self.clock += dt.total_seconds()
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
        self._follow_pie(dt.total_seconds())

    def _follow_pie(self, seconds: float) -> None:
        """The ammo pie: whole is the most the weapon has held; a shot fired makes it swell; it floats
        after the head, above it unless the body lies there, then aside."""
        if self.weapon is not self._carried:
            self._carried, self.ammo_full = self.weapon, 0
            self._ammo_before = self.weapon.ammo if self.weapon is not None else 0
        self.pie_kick = max(self.pie_kick - seconds, 0.0)
        if self.weapon is not None:
            ammo = self.weapon.ammo
            if ammo < self._ammo_before and self.ammo_full:
                self.pie_kick = PIE_KICK
            self._ammo_before = ammo
            self.ammo_full = max(self.ammo_full, ammo)
        head = self.head.pos
        spots = [Vec2(0, -PIE_ABOVE), Vec2(-PIE_ASIDE, -PIE_ABOVE / 2), Vec2(PIE_ASIDE, -PIE_ABOVE / 2)]
        clear = PIE_RADIUS + self.size + 2
        target = head + spots[0]
        near = self.segs[1:40] if self.weapon is not None else ()  # only the body near the head can be in the way
        for spot in spots:
            if not any((seg.pos - (head + spot)).length() < clear for seg in near):
                target = head + spot
                break
        self.pie = target if self.pie is None else self.pie + (target - self.pie) * PIE_FOLLOW

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
