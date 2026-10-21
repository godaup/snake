"""The Workshop (arc 7): crates the head pushes, plates and gates, keys carried in the body, belts and levers, and the
plan bots follow through a puzzle. The entities register like those in entity.py (which imports this module at its
end); `Works` is the map's part (`map.works`, built when a level has any of it).

The bench grid: crates, plates, gates and the rest lie on 16 px cells (two tiles), counted from the map's corner."""

from collections import deque
from copy import copy
from typing import TYPE_CHECKING

import pyxel

from snake_quest.entity import Apple, Entity, GoldenApple, Hunter, Nest, register
from snake_quest.tiles import (
    BELT_TILES,
    GATE_OPEN_TILES,
    GATE_TILES,
    HAZARD_TILE,
    LEVER_TILES,
    LOCK_TILES,
    PLATE_TILES,
    RESET_TILE,
    WALL_TILES,
)
from snake_quest.utils import Vec2, collision_points

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake

CELL = 16  # px: the bench grid
GLIDE = 1.0  # px per frame a crate the head let go of slides on to the grid
GATE_WARN = 0.6  # seconds an open gate blinks before it shuts, once its plates are let go of
COL_WARN = 8
BELT = 0.6  # px per frame a belt carries what lies on it (times the difficulty's speed; a level may set `belt`)
KEY_COLS = (8, 12, 10)  # red, blue, yellow
PRESSED_COLS = (2, 5, 9)  # a pressed plate sinks: red, blue, yellow darker
COL_BELT = 13
BELT_REVERSED = {(28, 10): (30, 10), (30, 10): (28, 10), (29, 10): (31, 10), (31, 10): (29, 10)}


@register("crate")
class Crate(Entity):
    """A 16x16 crate: the head pushes it along the bench grid's axes (see Works.push), and once let go it glides on to
    the nearest cell. It can't be eaten or shot, and it never hurts the snake: one that can't move stops it."""

    _img_x = 3  # 2x2 sprite tiles from here
    _img_y = 21
    block = True
    tally = False
    fixed = False  # never moves (the Clockwork): the head stops at it like at a crate that can't be pushed

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.w = self.h = CELL
        self.start = Vec2(self.pos.x, self.pos.y)  # where the reset lever puts it back
        self.axis = (0, 0)  # the way it last moved
        self.pushed = False  # moved by the head this frame: no gliding

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(CELL / 2, CELL / 2)

    def update(self, snake: "Snake", map: "Map"):
        works = map.works
        if self.pushed or works is None or self.fixed:
            self.pushed = False
            return
        drift = works.drift_at(self.center)
        if drift.x or drift.y:  # carried by a belt
            self.axis = (int(drift.x > 0) - int(drift.x < 0), int(drift.y > 0) - int(drift.y < 0))
            if works.free(self, self.pos + drift, snake):
                self.pos = self.pos + drift
                return
        self._settle(works, snake)

    def _settle(self, works: "Works", snake: "Snake") -> None:
        """Slide to the nearest cell along the way it last moved (or back, when that is taken)."""
        origin = works.origin
        for axis, value, base in ((0, self.pos.x, origin.x), (1, self.pos.y, origin.y)):
            offset = (value - base) % CELL
            if offset == 0:
                continue
            ahead = CELL - offset
            moves = (ahead, -offset) if ahead <= offset else (-offset, ahead)
            for move in moves:
                step = max(-GLIDE, min(GLIDE, move))
                pos = Vec2(self.pos.x + step, self.pos.y) if axis == 0 else Vec2(self.pos.x, self.pos.y + step)
                if works.free(self, pos, snake):
                    self.pos = pos
                    break


class Key(Entity):
    """A key of one colour: eaten, it rides in the body as a segment of its own at the tail (`seg.key`); the head
    touching a lock of its colour opens it and uses the key up. Whatever cuts the body behind it drops it again."""

    light = 12
    pullable = True
    COLOUR = 0  # index into KEY_COLS, LOCK_TILES
    POINTS = 1

    def on_intersect(self, snake: "Snake", map: "Map"):
        from snake_quest.snake import SnakeSeg

        seg = SnakeSeg(copy(snake.segs[-1].pos), snake.size, snake.body_color(len(snake)))
        seg.key = self.COLOUR
        snake.segs.append(seg)
        map.game.score += self.POINTS
        map.game.sm.effect("pickup")
        self.alive = False


@register("key_red")
class RedKey(Key):
    _img_x = 5
    _img_y = 21
    COLOUR = 0


@register("key_blue")
class BlueKey(Key):
    _img_x = 5
    _img_y = 22
    COLOUR = 1


@register("key_yellow")
class YellowKey(Key):
    _img_x = 6
    _img_y = 22
    COLOUR = 2


KEYS = (RedKey, BlueKey, YellowKey)


@register("mouse")
class Mouse(Hunter):
    """A clockwork mouse: a beetle that goes for the key nearest the tail rather than the tail (and for the tail when
    the body carries none). Its bite cuts the body where it bites, so a key behind it falls off; bitten next to the
    head, it is the end. Thorns break it."""

    _img_x = 6
    _img_y = 21
    ASLEEP_IMG_X = 7  # wound up, not yet running
    SPEED = 1.2
    DETOUR_CHANCE = 0.3
    BITE = 4
    NECK = 4  # segments behind the head: a bite there is the end

    def quarry(self, snake: "Snake", map: "Map") -> tuple[dict[tuple[int, int], int], Vec2]:
        keys = [seg for seg in snake.segs if getattr(seg, "key", None) is not None]
        if not keys:
            return super().quarry(snake, map)
        return map.field("keys", keys[-1].pos), keys[-1].pos

    def update(self, snake: "Snake", map: "Map"):
        super().update(snake, map)
        if map.tile_at(self.center) == HAZARD_TILE:  # thorns
            self.alive, self.killed = False, True

    def bite(self, snake: "Snake", map: "Map") -> None:
        map.game.sm.effect("hurt")
        self._begin("retreat", self.RETREAT)
        near = [(i, (seg.pos - self.center).length()) for i, seg in enumerate(snake.segs)]
        index, distance = min(near, key=lambda item: item[1])  # where it bites: the segment nearest to it
        if distance >= self.BITE:
            return
        if index <= self.NECK:
            map.snake_killed = True
            return
        snake.segs = snake.segs[:index]


@register("mousehole")
class MouseHole(Nest):
    """A hole in the skirting board that clockwork mice run out of (a Nest)."""

    _img_x = 7
    _img_y = 22
    BROOD_CLS = Mouse
    SPAWN = 8.0
    BROOD = 2
    ALERT = 140


class Works:
    """The Workshop's machinery on a map: plates (one per bench grid cell, so plates side by side count apart), the
    gates and locks of each colour, belts, levers and reset levers, and the rooms between gates (a flood fill counting
    gates and locks as walls). Updated every frame after the snake moved (see Map.update)."""

    def __init__(self, map: "Map"):
        self.map = map
        self.origin = Vec2(0, map.header)  # the bench grid's corner
        self.belt = float(map.cfg.get("belt", BELT)) * map.game.difficulty.speed
        tilemap = pyxel.tilemaps[map.tm]
        width, height = map.cfg.width // 8, map.cfg.height // 8
        tiles = {(x, y): tilemap.pget(x, y) for y in range(height) for x in range(width)}
        cells: dict[tuple[int, int, int], set[tuple[int, int]]] = {}  # a plate per bench grid cell and colour
        for (x, y), sprite in tiles.items():
            if sprite in PLATE_TILES:
                cells.setdefault((x // 2, y // 2, PLATE_TILES.index(sprite)), set()).add((x, y))
        self.plates: list[tuple[int, set[tuple[int, int]]]] = [(colour, group) for (*_, colour), group in cells.items()]
        self.gates: dict[int, list[tuple[int, int]]] = {}
        for tile, sprite in tiles.items():
            for colour in range(3):
                if sprite in (GATE_TILES[colour], GATE_OPEN_TILES[colour]):
                    self.gates.setdefault(colour, []).append(tile)
        self.belts = {tile for tile, sprite in tiles.items() if sprite in BELT_TILES}
        self.rooms: dict[tuple[int, int], int] = {}
        separators = WALL_TILES | set(GATE_OPEN_TILES)
        for tile, sprite in tiles.items():
            if sprite not in separators and tile not in self.rooms:
                self._group(tiles, tile, None, separators, room=len(set(self.rooms.values())))
        self.crates: list[Crate] = [ent for ent in map.entities if isinstance(ent, Crate)]
        self.down: set[int] = set()  # indices of the plates that are down
        self.warning: dict[int, float] = {}  # colour -> seconds until its gate shuts (its plates were let go of)
        self.closing: set[tuple[int, int]] = set()  # the tiles of those gates (blinking)
        self.carried: dict[int, tuple] = {}  # id of a key segment -> (segment, colour, last position)
        self.keys: set[int] = set()  # colours the body carries
        self._head_on: str | None = None  # the kind of lever the head is on (it acts when the head gets onto it)
        self.levers = [tile for tile, sprite in tiles.items() if sprite in (*LEVER_TILES, RESET_TILE)]
        self.plan = Plan(map.cfg.plan, self) if "plan" in map.cfg else None

    def _group(self, tiles, start, sprites=None, separators=None, room=None) -> set[tuple[int, int]]:
        """The tiles connected to `start`: of the same `sprites`, or (for a room) all but the `separators`."""
        group, queue = {start}, deque([start])
        while queue:
            x, y = queue.popleft()
            for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nxt in group or nxt not in tiles:
                    continue
                if (sprites is not None and tiles[nxt] not in sprites) or (
                    separators is not None and tiles[nxt] in separators
                ):
                    continue
                group.add(nxt)
                queue.append(nxt)
        if room is not None:
            for tile in group:
                self.rooms[tile] = room
        return group

    def room_of(self, pos: Vec2) -> int | None:
        return self.rooms.get(self.map.tile_xy(pos))

    # -- every frame

    def update(self, snake: "Snake") -> None:
        map = self.map
        tilemap = pyxel.tilemaps[map.tm]
        covered = {map.tile_xy(seg.pos) for seg in snake.segs}
        held = covered | {tile for crate in self.crates if crate.alive for tile in self._tiles(crate.pos)}
        self.down = {index for index, (_, group) in enumerate(self.plates) if group & held}
        seconds = map.game.dt.total_seconds()
        for colour, gate in self.gates.items():
            plates = [index for index, (plate_colour, _) in enumerate(self.plates) if plate_colour == colour]
            if not plates:
                continue  # opened by something else (a lock, the boss)
            wanted = all(index in self.down for index in plates)
            jammed = any(tile in held for tile in gate)  # a gate never shuts on the snake or a crate
            opened = tilemap.pget(*gate[0]) == GATE_OPEN_TILES[colour]
            if wanted or jammed or not opened:
                self.warning.pop(colour, None)
            else:  # let go of: it blinks for GATE_WARN seconds, then shuts
                self.warning[colour] = self.warning.get(colour, GATE_WARN) - seconds
            for tile in gate:
                shut = tilemap.pget(*tile) == GATE_TILES[colour]
                if wanted and shut:
                    self._set(tile, GATE_OPEN_TILES[colour])
                elif not shut and self.warning.get(colour, 1) <= 0:
                    self._set(tile, GATE_TILES[colour])
            if self.warning.get(colour, 1) <= 0:
                del self.warning[colour]
        self.closing = {tile for colour in self.warning for tile in self.gates[colour]}
        if not map.doors:  # bots keep out of what is about to shut (the airlock doors' set)
            map.closing = self.closing
        # what the head runs onto: levers and reset levers (once per lever, however many of its tiles it crosses)
        sprite = map.tile_at(snake.head.pos)
        kind = "lever" if sprite in LEVER_TILES else "reset" if sprite == RESET_TILE else None
        if kind != self._head_on:
            self._head_on = kind
            tile = map.tile_xy(snake.head.pos)
            if kind == "lever":
                self.flip(self.rooms.get(tile))
            elif kind == "reset":
                self.reset(self.rooms.get(tile), snake)
        # locks: the head bringing a key of their colour
        for point in snake.get_collision_points():
            sprite = map.tile_at(point)
            if sprite in LOCK_TILES and LOCK_TILES.index(sprite) in self.keys:
                self.unlock(map.tile_xy(point), snake)
        self._count_keys(snake)

    def _count_keys(self, snake: "Snake") -> None:
        """Keep track of the key segments: one no longer in the body (cut off) drops its key where it was."""
        present = {id(seg) for seg in snake.segs}
        for ident, (seg, colour, pos) in list(self.carried.items()):
            if ident not in present:
                del self.carried[ident]
                if colour is not None:  # not used up by a lock
                    self.map.entities.append(KEYS[colour].at_pos(pos - Vec2(4, 4)))
            else:
                self.carried[ident] = (seg, colour, copy(seg.pos))
        for seg in snake.segs:
            if getattr(seg, "key", None) is not None and id(seg) not in self.carried:
                self.carried[id(seg)] = (seg, seg.key, copy(seg.pos))
        self._recount()

    def _recount(self) -> None:
        """The colours carried; when they change, which locks are walls changes too (bots' caches start over)."""
        keys = {colour for _, colour, _ in self.carried.values() if colour is not None}
        if keys != self.keys:
            self.keys = keys
            self.map.walls_version += 1
            self.map._fields.clear()

    def _set(self, tile: tuple[int, int], sprite: tuple[int, int]) -> None:
        pyxel.tilemaps[self.map.tm].pset(*tile, sprite)
        self.map._walls_changed(tile)

    def _tiles(self, pos: Vec2) -> set[tuple[int, int]]:
        """The tiles a crate at `pos` presses (those whose centre it covers)."""
        x0, y0 = int(pos.x + 4) // 8, int(pos.y - self.map.header + 4) // 8
        return {(x, y) for x in (x0, x0 + 1) for y in (y0, y0 + 1)}

    # -- what the head does

    def unlock(self, tile: tuple[int, int], snake: "Snake") -> None:
        """Open the lock at `tile` (all its tiles) for good, using up the key of its colour nearest the head."""
        tilemap = pyxel.tilemaps[self.map.tm]
        sprite = tilemap.pget(*tile)
        colour = LOCK_TILES.index(sprite)
        tiles = {
            (x, y): tilemap.pget(x, y) for x in range(tile[0] - 8, tile[0] + 9) for y in range(tile[1] - 8, tile[1] + 9)
        }
        for lock in self._group(tiles, tile, {sprite}):
            self._set(lock, GATE_OPEN_TILES[colour])
        seg = next(seg for seg in snake.segs if getattr(seg, "key", None) == colour)
        seg.key = None
        self.carried[id(seg)] = (seg, None, seg.pos)
        snake.segs.remove(seg)
        self._recount()
        self.map.game.sm.effect("portal")

    def unlocks(self, sprite: tuple[int, int]) -> bool:
        """Whether a wall tile is a lock the body carries the key for (then it isn't a wall to the head)."""
        return sprite in LOCK_TILES and LOCK_TILES.index(sprite) in self.keys

    def flip(self, room: int | None) -> None:
        """A lever thrown: every lever of the room flips and every belt of the room turns round."""
        tilemap = pyxel.tilemaps[self.map.tm]
        for tile, other in self.rooms.items():
            if other != room:
                continue
            sprite = tilemap.pget(*tile)
            if sprite in LEVER_TILES:
                tilemap.pset(*tile, LEVER_TILES[1 - LEVER_TILES.index(sprite)])
            elif sprite in BELT_REVERSED:
                tilemap.pset(*tile, BELT_REVERSED[sprite])
        self.map.game.sm.effect("pickup")

    def reset(self, room: int | None, snake: "Snake") -> None:
        """The reset lever: the room's crates back where they started (where that spot is free)."""
        for crate in self.crates:
            if crate.alive and self.room_of(crate.start + Vec2(4, 4)) == room and self.free(crate, crate.start, snake):
                crate.pos = Vec2(crate.start.x, crate.start.y)
        if self.plan is not None:
            self.plan.on_reset(room)
        self.map.game.sm.effect("portal")

    def drift_at(self, pos: Vec2) -> Vec2:
        """The belt's push at `pos` (px per frame), or none."""
        direction = BELT_TILES.get(self.map.tile_at(pos)) if self.belts else None
        return Vec2(direction[0] * self.belt, direction[1] * self.belt) if direction else Vec2(0, 0)

    def push(self, snake: "Snake", step: Vec2) -> Vec2 | None:
        """The head about to move by `step`: a crate it runs into head on moves along the axis of the face it meets,
        as far as the head goes into it; one it meets at a glance (more along the face than into it) lets it slide
        along. The step to take, or None when a crate can't move (all the way): the snake stalls (doesn't move)."""
        head, size = snake.head.pos, snake.size
        new = head + step
        p, q = collision_points(new, pyxel.atan2(step.y, step.x), size)
        for crate in self.crates:
            if not crate.alive or not (crate.covers(p) or crate.covers(q) or crate.covers(new)):
                continue
            x0, y0 = crate.pos.x, crate.pos.y
            x1, y1 = x0 + crate.w, y0 + crate.h
            faces = []
            if head.x < x0 and step.x > 0:
                faces.append((step.x, (1, 0), new.x + size - x0))
            if head.x > x1 and step.x < 0:
                faces.append((-step.x, (-1, 0), x1 - (new.x - size)))
            if head.y < y0 and step.y > 0:
                faces.append((step.y, (0, 1), new.y + size - y0))
            if head.y > y1 and step.y < 0:
                faces.append((-step.y, (0, -1), y1 - (new.y - size)))
            if not faces:
                continue
            into, axis, depth = max(faces)
            if into < abs(step.x * axis[1]) + abs(step.y * axis[0]):  # glancing: slide along the face
                step = Vec2(step.x * axis[1] * axis[1], step.y * axis[0] * axis[0])
                new = head + step
                continue
            depth = max(depth, 0.0)
            moved = self._shove(crate, axis, depth, snake)
            crate.pushed, crate.axis = True, axis
            if moved < depth - 0.01:
                return None
        return step

    def _shove(self, crate: Crate, axis: tuple[int, int], depth: float, snake: "Snake") -> float:
        """Move `crate` up to `depth` px along `axis`, as far as it is free; how far it went."""
        moved, step = 0.0, 0.25
        while moved < depth and not crate.fixed:
            amount = min(step, depth - moved)
            pos = crate.pos + Vec2(axis[0] * amount, axis[1] * amount)
            if not self.free(crate, pos, snake):
                break
            crate.pos, moved = pos, moved + amount
        return moved

    def free(self, crate: Crate, pos: Vec2, snake: "Snake | None") -> bool:
        """Whether `crate` fits at `pos`: no wall (shut gates and locks are walls), no other crate, no segment but the
        head's."""
        map = self.map
        for x in (pos.x + 0.5, pos.x + CELL / 2, pos.x + CELL - 0.5):
            for y in (pos.y + 0.5, pos.y + CELL / 2, pos.y + CELL - 0.5):
                if map.tile_at(Vec2(x, y)) in WALL_TILES:
                    return False
        for other in self.crates:
            if (
                other is not crate
                and other.alive
                and other.pos.x - CELL < pos.x < other.pos.x + other.w
                and other.pos.y - CELL < pos.y < other.pos.y + other.h
            ):
                return False
        if snake is not None:  # a segment the crate would move onto (not one it moves away from)
            reach = snake.size - 0.5

            def inside(at: Vec2, seg) -> bool:
                return at.x - reach < seg.pos.x < at.x + CELL + reach and at.y - reach < seg.pos.y < at.y + CELL + reach

            if any(inside(pos, seg) and not inside(crate.pos, seg) for seg in snake.segs[1:]):
                return False
        return True

    def draw(self, offset: Vec2) -> None:
        """Pressed plates sink (darker), and belts show which way they run (chevrons moving along)."""
        map, header = self.map, self.map.header
        if self.closing and pyxel.frame_count % 6 < 3:  # gates about to shut blink
            for x, y in self.closing:
                pyxel.rectb(x * 8 + offset.x, y * 8 + header + offset.y, 8, 8, COL_WARN)
        for index in self.down:
            for x, y in self.plates[index][1]:
                pyxel.rect(
                    x * 8 + 2 + offset.x, y * 8 + header + 2 + offset.y, 4, 4, PRESSED_COLS[self.plates[index][0]]
                )
        if not self.belts:
            return
        tilemap = pyxel.tilemaps[map.tm]
        shift = int(pyxel.frame_count * max(self.belt, 0.2)) % 8
        left, top = -offset.x - 8, -offset.y - 8
        right, bottom = left + map.game.cfg.width + 16, top + map.game.cfg.area.h + 16
        for x, y in self.belts:
            if not (left <= x * 8 <= right and top <= y * 8 + header <= bottom):
                continue
            dx, dy = BELT_TILES.get(tilemap.pget(x, y), (0, 0))
            sx, sy = x * 8 + offset.x, y * 8 + header + offset.y
            if dx:
                lx = sx + (shift if dx > 0 else 7 - shift)
                pyxel.line(lx, sy + 1, lx, sy + 6, COL_BELT)
            elif dy:
                ly = sy + (shift if dy > 0 else 7 - shift)
                pyxel.line(sx + 1, ly, sx + 6, ly, COL_BELT)


DIRECTIONS = {"right": (1, 0), "down": (0, 1), "left": (-1, 0), "up": (0, -1)}
PLAN_PATIENCE = 45.0  # seconds a step may take; then the room starts again (its reset lever)
APPROACH = 64  # px behind a crate (at most) a push is approached from, so the snake meets it straight
LINE_UP = 16  # px off the push line at most while lining up
LEAD = 12  # px ahead along the line it steers for while lining up
ALIGN = 40  # degrees: heading at most this far off the push at the face (a push needs 45), else it comes round again
ENTER = 90  # degrees: heading at most this far off the push to start lining up
NEAR = 6  # px: a point counts as visited


class Plan:
    """The steps of a puzzle's solution, which only bots read (the level's `plan`): a list of rooms, each with its
    reset lever's cell and its steps:

        plan:
          - reset: [2, 5]
            steps:
              - push: [[5, 3], right, 2]  # the crate on cell (5, 3) two cells to the right
              - visit: [14, 3]            # a cell to cross: a plate, a lever, a gate
              - grow: 30                  # eat until 30 long
              - key: blue                 # fetch the nearest blue key
              - unlock: [20, 6]           # touch the lock on cell (20, 6)
              - wait: {at: [8, 4], crate: [12, 4]}  # about a cell until a crate rests on (12, 4) (or gate: red,
                                                    # or seconds: s)
              - bring: [12, 9]            # run into what is on that cell (the Clockwork) until its key is taken

    Cells are bench grid cells (16 px). A step that doesn't come true within PLAN_PATIENCE seconds sends the bot over
    the room's reset lever (`reset: null`: none), and the room's steps start again. `grow` eats in the bot's room only
    (apples elsewhere may lie behind shut gates)."""

    COLOURS = ("red", "blue", "yellow")

    def __init__(self, cfg, works: Works):
        self.works = works
        self.rooms = [(room.get("reset"), list(room.steps)) for room in cfg]
        self.room = 0
        self.index = 0
        self.stage = 0  # within a push: 0 heading for the approach point, 1 lining up, 2 pushing, 3 turning off
        self.since = 0.0  # seconds on the current step
        self.resetting = False
        self.start: Vec2 | None = None  # a pushed crate's position when the push began
        self.pushing: Crate | None = None  # the crate being pushed (bots don't count it as a block then)

    @property
    def done(self) -> bool:
        return self.room >= len(self.rooms)

    def cell(self, cell) -> Vec2:
        """The world centre of a bench grid cell."""
        origin = self.works.origin
        return Vec2(origin.x + cell[0] * CELL + CELL / 2, origin.y + cell[1] * CELL + CELL / 2)

    def on_reset(self, room: int | None) -> None:
        """The room's crates went back: its steps start again."""
        if self.done:
            return
        reset = self.rooms[self.room][0]
        if reset is not None and self.works.room_of(self.cell(reset)) == room:
            self.index, self.stage, self.since, self.resetting, self.pushing = 0, 0, 0.0, False, None

    def _next(self) -> None:
        self.index, self.stage, self.since, self.pushing = self.index + 1, 0, 0.0, None
        if self.index >= len(self.rooms[self.room][1]):
            self.room, self.index = self.room + 1, 0

    def target(self, snake: "Snake", map: "Map") -> Vec2 | None:
        """Where the bot heads for this frame, or None once the plan is done (the exit, and the rest, then)."""
        self.since += map.game.dt.total_seconds()  # bots ask once per frame
        while not self.done:
            reset = self.rooms[self.room][0]
            if self.since > PLAN_PATIENCE:  # stuck: the room again, from its reset lever if it has one
                if reset is None:
                    self.index, self.stage, self.since, self.pushing = 0, 0, 0.0, None
                else:
                    self.resetting = True
            if self.resetting:
                return self.cell(reset)
            step = self.rooms[self.room][1][self.index]
            point = self._step(step, snake, map)
            if point is not None:
                return point
            self._next()
        return None

    def _step(self, step, snake: "Snake", map: "Map") -> Vec2 | None:
        """The point to head for, or None when the step is done."""
        head = snake.head.pos
        kind, value = next(iter(step.items())) if not isinstance(step, str) else (step, None)
        if kind in ("visit", "lever"):
            point = self.cell(value)
            return None if (point - head).length() < NEAR else point
        if kind == "grow":
            if len(snake) >= value:
                return None
            here = self.works.room_of(head)
            foods = [
                ent.pos + Vec2(4, 4)
                for ent in map.entities
                if ent.alive
                and isinstance(ent, (Apple, GoldenApple))
                and self.works.room_of(ent.pos + Vec2(4, 4)) == here
            ]
            return min(foods, key=lambda pos: (pos - head).length(), default=head)
        if kind == "key":
            colour = self.COLOURS.index(value)
            if colour in self.works.keys:
                return None
            from snake_quest.controls import nearest

            return nearest(KEYS[colour], clearance=0)(snake, map) or head
        if kind == "unlock":
            point = self.cell(value)
            return None if map.tile_at(point) not in LOCK_TILES else point
        if kind == "bring":  # touch a fixed block (the Clockwork) while the body carries a key, until it is taken
            return self.cell(value) if self.works.keys else None
        if kind == "wait":
            if "crate" in value and any(
                (crate.center - self.cell(value.crate)).length() < 1 for crate in self.works.crates
            ):
                return None
            if "gate" in value:
                colour = self.COLOURS.index(value.gate)
                if any(
                    pyxel.tilemaps[map.tm].pget(*tile) == GATE_OPEN_TILES[colour] for tile in self.works.gates[colour]
                ):
                    return None
            if "seconds" in value and self.since >= value.seconds:
                return None
            return self.cell(value.at)
        if kind == "push":
            return self._push(value, snake, map)
        raise ValueError(f"unknown plan step {kind!r}")

    def _push(self, value, snake: "Snake", map: "Map") -> Vec2 | None:
        cell, direction, cells = value
        d = DIRECTIONS[direction]
        if self.pushing is None:  # the crate on that cell
            centre = self.cell(cell)
            crate = min(self.works.crates, key=lambda crate: (crate.center - centre).length())
            if (crate.center - centre).length() > CELL / 2:  # it has gone (a boss threw it): nothing to push
                return None
            self.pushing, self.start = crate, Vec2(crate.pos.x, crate.pos.y)
        crate = self.pushing
        moved = (crate.pos.x - self.start.x) * d[0] + (crate.pos.y - self.start.y) * d[1]
        head = snake.head.pos
        if moved >= cells * CELL - CELL / 2 or self.stage == 3:  # far enough (it glides the rest): turn off it
            self.stage = 3
            box = (crate.pos.x - 4, crate.pos.y - 4, crate.pos.x + CELL + 4, crate.pos.y + CELL + 4)
            if not (box[0] <= head.x <= box[2] and box[1] <= head.y <= box[3]):
                return None
            sides = [Vec2(-d[1], d[0]), Vec2(d[1], -d[0])]
            room = [sum(not map.check_on_wall(head + side * r) for r in (8, 16, 24, 32)) for side in sides]
            return head + sides[room.index(max(room))] * 48
        if self.stage == 2:  # pushing; given up when it went past (back to lining up)
            if (head - crate.center).length() > APPROACH + CELL:
                self.stage = 0
            beyond = cells * CELL + CELL / 2  # just past the goal cell
            return self.start + Vec2(CELL / 2 + d[0] * beyond, CELL / 2 + d[1] * beyond)
        # where the head is: `along` the push line (negative behind the crate) and to its `side`
        offset = head - crate.center
        along, side = offset.x * d[0] + offset.y * d[1], offset.y * d[0] - offset.x * d[1]
        back = self._room_behind(crate, d, map)
        turn = abs((pyxel.atan2(d[1], d[0]) - snake.heading + 180) % 360 - 180)
        if self.stage == 0:
            if abs(side) < LINE_UP and -back - NEAR <= along <= -CELL and turn <= ENTER:
                self.stage = 1
            return crate.center - Vec2(d[0] * back, d[1] * back)
        # lining up: steer for the line a little ahead of the head, and push once straight and on it at the face
        face = CELL / 2 + snake.size + 2
        if abs(side) > LINE_UP or along > -face + 2:
            self.stage = 0
            return crate.center - Vec2(d[0] * back, d[1] * back)
        if along >= -face - NEAR:
            self.stage = 2 if turn <= ALIGN and abs(side) < CELL / 2 - snake.size else 0
        ahead = along + LEAD  # on into the crate (not stopping short: arcs reaching a point turn at random)
        return crate.center + Vec2(d[0] * ahead, d[1] * ahead)

    def _room_behind(self, crate: Crate, d: tuple[int, int], map: "Map") -> float:
        """How far behind the crate (px from its centre, at most APPROACH) the push line is free."""
        room = CELL
        for back in range(CELL, APPROACH + 1, 4):
            point = crate.center - Vec2(d[0] * back, d[1] * back)
            if map.check_on_wall(point) or any(
                other is not crate and other.covers(point) for other in self.works.crates
            ):
                break
            room = back
        return max(CELL, room - 8)

    def avoid(self) -> list[tuple[int, int]]:
        """Lever tiles bots keep off (throwing one by chance undoes the plan), but not the one the plan heads for."""
        aim = None
        if not self.done:
            step = self.rooms[self.room][1][self.index]
            kind, value = next(iter(step.items())) if not isinstance(step, str) else (step, None)
            aim = self.rooms[self.room][0] if self.resetting else value if kind in ("visit", "lever") else None
        here = None if aim is None else (int(aim[0]) * 2, int(aim[1]) * 2)
        return [
            tile
            for tile in self.works.levers
            if here is None or not (0 <= tile[0] - here[0] <= 1 and 0 <= tile[1] - here[1] <= 1)
        ]

    def blocks(self) -> list[Crate]:
        """The crates bots keep out of: all but the one they are pushing (once lined up), and not what they bring a
        key to."""
        step = self.rooms[self.room][1][self.index] if not self.done else {}
        bringing = isinstance(step, dict) and "bring" in step
        return [
            crate
            for crate in self.works.crates
            if crate.alive and not (crate is self.pushing and self.stage >= 1) and not (bringing and crate.fixed)
        ]


@register("clockwork")
class Clockwork(Crate):
    """The Clockwork (level 35, put in by the `clockwork` boss): a 32x32 machine that never moves (the head stops at
    it, as at a crate that can't be pushed). Its face is shut (shots glint off) except while the boss opens it; it
    flashes when hit there. Its two hands are drawn from its centre at the boss's angles."""

    _img_x = 8  # 4x4 sprite tiles from here
    _img_y = 21
    hostile = True
    avoid = False  # bots keep off its hands (the boss's danger), not off it
    fixed = True
    tally = True
    FLASH = 0.15
    COL_SHUT = 13
    COL_CORE = 8
    COL_HANDS = (7, 10)  # the long hand, the short one

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.w = self.h = 2 * CELL
        self.open = False
        self.flash = 0.0
        self.glint = 0.0
        self.hands: list[tuple[float, float]] = []  # (angle, length) of each hand, set by the boss
        self.locks: list[int | None] = []  # lock colours still shut on the face (phase 3), set by the boss

    @property
    def exposed(self) -> bool:
        return self.open

    @property
    def center(self) -> Vec2:
        return self.pos + Vec2(CELL, CELL)

    def update(self, snake: "Snake", map: "Map"):
        seconds = map.game.dt.total_seconds()
        self.flash = max(self.flash - seconds, 0.0)
        self.glint = max(self.glint - seconds, 0.0)

    def hit(self, dmg: int):
        if not self.open:
            self.deflect()
            return
        super().hit(dmg)
        self.flash = self.FLASH

    def deflect(self):
        self.glint = 0.12

    def draw(self, offset: "Vec2"):
        if not self.alive:
            return
        if not (self.flash > 0 and pyxel.frame_count % 2):
            Entity.draw(self, offset)
        c = self.center + offset
        if self.open:
            pyxel.circ(c.x, c.y, 5, self.COL_CORE if pyxel.frame_count % 8 < 6 else 7)
        else:
            pyxel.circ(c.x, c.y, 5, 7 if self.glint > 0 else self.COL_SHUT)
            for i, colour in enumerate(self.locks):
                if colour is not None:
                    pyxel.circ(c.x - 6 + i * 6, c.y + 9, 1, KEY_COLS[colour])
        for (angle, length), col in zip(self.hands, self.COL_HANDS, strict=False):
            pyxel.line(c.x, c.y, c.x + pyxel.cos(angle) * length, c.y + pyxel.sin(angle) * length, col)
