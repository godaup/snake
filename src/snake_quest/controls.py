"""Input layer: what steers a snake. The player uses keyboard or gamepad; tests, bots and (later) the rival snake use
other controllers through the same interface, so `Snake` never reads input itself."""

import math
from collections import deque
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Optional

import pyxel

from snake_quest.utils import Vec2, collision_points

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake


class Controller:
    """Goes straight and never fires; subclasses override what they control."""

    def steer(self, snake: "Snake", map: Optional["Map"]) -> float:
        """Turn this frame: -1 (full left, see `snake.turn_speed`) .. 1 (full right)."""
        return 0.0

    def fire(self, snake: "Snake", map: Optional["Map"]) -> bool:
        """Shoot this frame (if the snake has a weapon that is ready)."""
        return False


class KeyboardController(Controller):
    """The player: arrow keys or d-pad to steer, space to shoot."""

    def steer(self, snake, map):
        if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT):
            return -1.0
        if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT):
            return 1.0
        return 0.0

    def fire(self, snake, map):
        return pyxel.btnp(pyxel.KEY_SPACE)


class ScriptedController(Controller):
    """Plays back one steering value per frame, then goes straight; fires on the given frames. For tests."""

    def __init__(self, steering: Iterable[float] = (), fire_frames: Iterable[int] = ()):
        self.steering = list(steering)
        self.fire_frames = set(fire_frames)
        self.frame = -1  # advanced by steer(), which the snake asks first every frame

    def steer(self, snake, map):
        self.frame += 1
        return self.steering[self.frame] if self.frame < len(self.steering) else 0.0

    def fire(self, snake, map):
        return self.frame in self.fire_frames


class ChaseController(Controller):
    """Steers towards a target as directly as the snake can turn, e.g. the demo snake in the menu or a bot.
    `target(snake, map)` gives the point to chase this frame, or None to go straight."""

    def __init__(self, target: Callable[["Snake", Optional["Map"]], Vec2 | None]):
        self.target = target

    def steer(self, snake, map):
        goal = self.target(snake, map)
        if goal is None:
            return 0.0
        to_goal = goal - snake.head.pos
        if to_goal.length() == 0:
            return 0.0
        wanted = pyxel.atan2(to_goal.y, to_goal.x)
        diff = (wanted - snake.orient + 180) % 360 - 180
        return max(-1.0, min(1.0, diff / snake.turn_speed))


class PathController(Controller):
    """A bot that takes the shortest way to `target(snake, map)`: around walls and its own body (a body cell counts as
    free once the tail will have left it by the time the head gets there), through portals. Every frame it tries a fan
    of steering values, each held for HORIZON frames, and drops the
    arcs that run into a wall or its own body, or that end where no hard turn or straight line gets it out again
    (ESCAPE frames). Once the snake is LONG, an arc must also leave room: a way to where the tail is leaving, or space
    for the whole body. Of the rest it takes the one ending closest to the target along the way; when none leaves room,
    it follows its tail until one does."""

    STEERING = (-1.0, -0.5, 0.0, 0.5, 1.0)
    ESCAPES = (0.0, -1.0, 1.0)
    HORIZON = 16  # frames looked ahead
    ESCAPE = 20  # frames an arc's end must leave room for
    BODY_SKIP = 6  # segments next to the head that can't be bitten
    LONG = 20  # segments: from this length on, arcs must also leave room to live in (see _room)
    ROOM = 8  # open cells needed per cell of body length
    CELL = 4  # px: grid of the room check
    ORBIT_PENALTY = 200  # px added to an arc that leaves the target inside its turning circle
    FIELD_EVERY = 3  # frames between recomputing the distances to the target
    REACH = 5  # px: an arc passing this close to the target gets it (entities are 8 px wide)

    def __init__(self, target: Callable[["Snake", "Map"], Vec2 | None]):
        self.target = target
        self._goal_cell: tuple[int, int] | None = None
        self._distance: dict[tuple[int, int], int] = {}  # cell -> steps to the target
        self._age = 0  # frames since the distances were computed
        self._walls: dict[tuple[int, int], bool] = {}  # cell -> wall, cached per map
        self._walls_map = None
        self.mode = ""  # why the last steering was chosen: goal, tail, escape or crash (for debugging)

    def steer(self, snake, map):
        goal = self.target(snake, map)
        if goal is None:
            self.mode = ""
            return 0.0
        goal_cell = self._cell(goal)
        self._age += 1
        if goal_cell != self._goal_cell or self._age >= self.FIELD_EVERY:
            self._goal_cell, self._distance, self._age = goal_cell, self._field(snake, map, goal_cell), 0
        arcs = {
            steering: self._arc(snake, map, snake.head.pos, snake.orient, steering, self.HORIZON, goal)
            for steering in self.STEERING
        }
        safe = [steering for steering, (survived, *_) in arcs.items() if survived == self.HORIZON]
        if not safe:  # crashing anyway: as late as possible
            self.mode = "crash"
            return max(arcs, key=lambda steering: arcs[steering][0])

        # turning circle: a target inside the circle on the side the snake turns to can't be reached by turning on, only
        # by straightening out first; without this the bot orbits the target until it bites its tail
        full_turn = snake.effective_speed / math.radians(snake.turn_speed)  # radius at full steering

        def distance(steering: float) -> float:
            """Way (px) left to the target from where the arc ends, plus ORBIT_PENALTY when it keeps circling; an arc
            passing over the target wins, the sooner the better."""
            _, pos, orient, reached = arcs[steering]
            if reached is not None:
                return reached - self.HORIZON * 100
            cost = self._distance.get(self._cell(pos), len(self._distance)) * self.CELL + (goal - pos).length()
            if steering:
                side, radius = (90 if steering > 0 else -90), full_turn / abs(steering)
                center = Vec2(pos.x + radius * pyxel.cos(orient + side), pos.y + radius * pyxel.sin(orient + side))
                if (goal - center).length() < radius:
                    cost += self.ORBIT_PENALTY
            return cost

        # the closest arc that leaves a way out (and, for a long snake, room to live in); the checks are the expensive
        # part, so only until one passes
        escapes, cramped = {}, []
        vacate = self._vacate(snake) if len(snake) >= self.LONG else None
        for steering in sorted(safe, key=distance):
            escapes[steering] = self._escape(snake, map, *arcs[steering][1:3])
            if escapes[steering] < self.ESCAPE:
                continue
            if vacate is None or self._room(snake, map, arcs[steering][1], vacate):
                self.mode = "goal"
                return steering
            cramped.append(steering)
        if cramped:  # no arc to the target leaves room: follow the tail until the way opens
            tail = snake.segs[-1].pos
            self.mode = "tail"
            return min(cramped, key=lambda steering: (arcs[steering][1] - tail).length())
        self.mode = "escape"
        return max(escapes, key=escapes.get)

    def _cell(self, pos: Vec2) -> tuple[int, int]:
        return int(pos.x) // self.CELL, int(pos.y) // self.CELL

    def _wall(self, map: "Map", cell: tuple[int, int]) -> bool:
        if map is not self._walls_map:
            self._walls, self._walls_map = {}, map
        if cell not in self._walls:
            center = Vec2(cell[0] * self.CELL + self.CELL / 2, cell[1] * self.CELL + self.CELL / 2)
            self._walls[cell] = map.check_on_wall(center)
        return self._walls[cell]

    def _field(self, snake: "Snake", map: "Map", goal: tuple[int, int]) -> dict[tuple[int, int], int]:
        """Steps (cells) from every reachable cell to the target cell, breadth first from the target. Walls block;
        a body cell blocks unless its last segment will have moved on by the time the head, going straight, could be
        there. A portal leads to the other one's centre."""
        vacate, head, speed = self._vacate(snake), snake.head.pos, snake.effective_speed

        def blocked(cell: tuple[int, int]) -> bool:
            if self._wall(map, cell):
                return True
            if cell in vacate:
                center = Vec2(cell[0] * self.CELL + self.CELL / 2, cell[1] * self.CELL + self.CELL / 2)
                return vacate[cell] > (center - head).length() / speed
            return False

        distance, queue = {goal: 0}, deque([goal])
        while queue:
            x, y = queue.popleft()
            nexts = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]
            partner = map.portals and map.portals.get(map.tile_xy(Vec2(x * self.CELL, y * self.CELL)))
            if partner:
                nexts.append(self._cell(map.tile_center(partner)))
            for nxt in nexts:
                if nxt not in distance and not blocked(nxt):
                    distance[nxt] = distance[x, y] + 1
                    queue.append(nxt)
        return distance

    def _vacate(self, snake: "Snake") -> dict[tuple[int, int], float]:
        """For every CELL-sized cell the body covers, and the cells next to it: frames until its last segment has moved
        on (each frame the segments shift by one; while growing, the tail stays). Counting the neighbours too keeps the
        bot out of gaps in its body that are too narrow to steer through."""
        vacate: dict[tuple[int, int], float] = {}
        n, grow = len(snake), max(snake.grow, 0)
        for index, seg in enumerate(snake.segs[1:], start=1):
            x, y = int(seg.pos.x) // self.CELL, int(seg.pos.y) // self.CELL
            frames = n - index + grow
            for cell in ((x, y), (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if vacate.get(cell, 0) < frames:
                    vacate[cell] = frames
        return vacate

    def _room(self, snake: "Snake", map: "Map", pos: Vec2, vacate: dict[tuple[int, int], float]) -> bool:
        """Whether the snake, at `pos` after HORIZON frames, still has room: a flood fill over CELL-sized cells (walls
        blocked, body cells passable once vacated by the time the head could get there) reaches where the tail is
        leaving, or enough open cells to hold the whole body."""
        speed = snake.effective_speed
        frames_per_cell = self.CELL / speed
        # space for the body (ROOM times the cells along its length) and for turning around in it
        turn = 2 * speed / math.radians(snake.turn_speed) / self.CELL
        needed = self.ROOM * len(snake) * speed / self.CELL + turn * turn
        start = (int(pos.x) // self.CELL, int(pos.y) // self.CELL)
        seen, queue, count = {start}, deque([(start, self.HORIZON)]), 0
        while queue:
            (x, y), frames = queue.popleft()
            count += 1
            if count >= needed:
                return True
            arrival = frames + frames_per_cell
            for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nxt in seen:
                    continue
                seen.add(nxt)
                center = Vec2(nxt[0] * self.CELL + self.CELL / 2, nxt[1] * self.CELL + self.CELL / 2)
                if map.check_on_wall(center):
                    continue
                if nxt in vacate:
                    if vacate[nxt] > arrival:
                        continue
                    return True  # behind the tail: it keeps making room
                queue.append((nxt, arrival))
        return False

    def _escape(self, snake: "Snake", map: "Map", pos: Vec2, orient: int) -> int:
        """Frames the best of a hard turn or a straight line survives from there (at most ESCAPE)."""
        best = 0
        for turn in self.ESCAPES:
            best = max(best, self._arc(snake, map, pos, orient, turn, self.ESCAPE)[0])
            if best == self.ESCAPE:
                break
        return best

    def _arc(
        self, snake: "Snake", map: "Map", pos: Vec2, orient: int, steering: float, frames: int, goal: Vec2 | None = None
    ):
        """Follow `steering` for `frames`: (frames survived, end position, end orientation, first frame within REACH
        of `goal` or None)."""
        reached = None
        speed, body = snake.effective_speed, snake.segs[self.BODY_SKIP :: 2]  # segments are ~1.3 px apart
        for frame in range(1, frames + 1):
            orient = (orient + round(steering * snake.turn_speed)) % 360
            pos = Vec2(pos.x + speed * pyxel.cos(orient), pos.y + speed * pyxel.sin(orient))
            p, q = collision_points(pos, orient, snake.size)
            near_body = frame % 2 == 0 and any((pos - seg.pos).length() < snake.size * 2 for seg in body)
            if map.check_on_wall(p) or map.check_on_wall(q) or near_body:
                return frame - 1, pos, orient, reached
            if reached is None and goal is not None and (goal - pos).length() < self.REACH:
                reached = frame
            partner = map.portals.get(map.tile_xy(pos))
            if partner is not None and partner != map.tile_xy(snake.head.pos):  # through the portal, as in the game
                pos = map.tile_center(partner)
        return frames, pos, orient, reached


def nearest(*classes: type, clearance: int = 1) -> Callable[["Snake", "Map"], Vec2 | None]:
    """Target for a ChaseController or PathController: the centre of the nearest live entity of these classes. Entities
    with a wall within `clearance` tiles (e.g. in a corner, hard to leave again) are only chosen when there is nothing
    else."""

    def open_around(map: "Map", pos: Vec2) -> bool:
        reach = range(-clearance, clearance + 1)
        return not any(map.check_on_wall(Vec2(pos.x + dx * 8, pos.y + dy * 8)) for dx in reach for dy in reach)

    def target(snake: "Snake", map: "Map") -> Vec2 | None:
        centres = [
            ent.pos + Vec2(ent.w / 2, ent.h / 2) for ent in map.entities if ent.alive and isinstance(ent, classes)
        ]
        safe = [pos for pos in centres if open_around(map, pos)]
        return min(safe or centres, key=lambda pos: (pos - snake.head.pos).length(), default=None)

    return target
