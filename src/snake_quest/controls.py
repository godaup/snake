"""Input layer: what steers a snake. The player uses keyboard or gamepad; tests, bots and (later) the rival snake use
other controllers through the same interface, so `Snake` never reads input itself."""

import math
from collections import deque
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Optional

import pyxel

from snake_quest.tiles import CRACK_TILE, HAZARD_TILE
from snake_quest.utils import Vec2, collision_points, drift

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
    BODY_SKIP = 6  # segments next to the head that can't be bitten (more while slowed: see Snake.neck)
    LONG = 20  # segments: from this length on, arcs must also leave room to live in (see _room)
    ROOM = 8  # open cells needed per cell of body length
    CELL = 4  # px: grid of the room check
    ORBIT_PENALTY = 200  # px added to an arc that leaves the target inside its turning circle
    FIELD_EVERY = 3  # frames between recomputing the distances to the target
    REACH = 5  # px: an arc passing this close to the target gets it (entities are 8 px wide)
    THREAT = 14  # px kept from an awake hostile entity (hunters), growing by THREAT_GROWTH per frame ahead
    THREAT_GROWTH = 1.0
    SLEEPER = 10  # px kept from a sleeping one
    AIM = 8  # degrees: shoots at a hostile entity this close to straight ahead (wider when it is near)
    AIM_AHEAD = 100  # degrees: only entities about ahead are aimed at
    DODGE = 5  # px kept from a hostile shot (turrets), along its flight
    TRAIL = 40  # px: a hostile entity this close to the tail gets a mine dropped in its way
    DEFENCE = 64  # px: while not hunting, it only turns to aim at hostile entities that never move this close
    AIM_PATIENCE = 48  # frames it turns to aim at most, then AIM_PATIENCE frames not (so it never circles forever)

    def __init__(self, target: Callable[["Snake", "Map"], Vec2 | None]):
        self.target = target
        self._goal_cell: tuple[int, int] | None = None
        self._distance: dict[tuple[int, int], int] = {}  # cell -> steps to the target
        self._age = 0  # frames since the distances were computed
        self._walls: dict[tuple[int, int], bool] = {}  # cell -> wall, cached per map
        self._walls_map = None
        self._walls_version = 0  # the map's walls_version the cache is for
        self.mode = ""  # why the last steering was chosen: goal, aim, tail, escape or crash (for debugging)
        self._threats: list[tuple[Vec2, float]] = []  # centre and radius to keep away from, per frame
        self._solids: list[tuple[Vec2, float]] = []  # the same for what never moves (see SOLID)
        self._shots: list[tuple[Vec2, Vec2]] = []  # position and velocity (px per frame) of hostile shots, per frame
        self._aiming = 0  # frames in a row spent turning to aim (and then counting down the pause)

    def steer(self, snake, map):
        """The steering chosen for the snake; on mirrored floor the other way round, as a player who knows it would."""
        steering = self._steer(snake, map)
        return -steering if snake.mirrored else steering

    BODY = 7  # px kept from every segment of another snake's body (a rival's)
    SOLID = 5  # px kept from the surface of something solid (`Entity.solid`: planets)

    def threats(self, snake, map) -> list[tuple[Vec2, float]]:
        """Centres and radii to keep away from: awake and sleeping hostile entities (bigger ones get a wider berth) and
        the body of a rival snake (an entity with a `body`); never the snake's own."""
        threats = []
        for ent in map.entities:
            if not (ent.alive and ent.hostile and ent.avoid):
                continue
            body = getattr(ent, "body", None)
            if body is snake:
                continue
            if body is not None:
                threats += [(seg.pos, self.BODY) for seg in body.segs[::2]]
                continue
            radius = (self.SLEEPER if getattr(ent, "asleep", False) else self.THREAT) + max(ent.w, ent.h) - 8
            threats.append((ent.pos + Vec2(ent.w / 2, ent.h / 2), radius))
        boss = getattr(map, "boss", None)
        danger = boss.danger() if boss is not None else None  # e.g. where the Brood Mother will land
        if danger is not None:
            threats.append(danger)
        return threats

    def _steer(self, snake, map):
        self._threats = self.threats(snake, map)
        # what never moves but is a crash to touch (planets): kept clear by SOLID px, however far ahead
        self._solids = [
            (ent.pos + Vec2(ent.w / 2, ent.h / 2), ent.RADIUS + self.SOLID)
            for ent in map.entities
            if ent.alive and ent.solid
        ]
        self._shots = [(shot.pos, shot.dir * shot.speed) for shot in map.projectiles if shot.alive and shot.hostile]
        goal = self.target(snake, map)
        if goal is None:
            self.mode = ""
            return 0.0
        goal_cell = self._cell(goal)
        self._age += 1
        if goal_cell != self._goal_cell or self._age >= self.FIELD_EVERY:
            self._goal_cell, self._distance, self._age = goal_cell, self._field(snake, map, goal_cell), 0
        arcs = {
            steering: self._arc(snake, map, snake.head.pos, snake.orient, steering, self.HORIZON, goal, snake.heading)
            for steering in self.STEERING
        }
        safe = [steering for steering, (survived, *_) in arcs.items() if survived == self.HORIZON]
        if not safe:  # crashing anyway: as late as possible
            self.mode = "crash"
            return max(arcs, key=lambda steering: arcs[steering][0])
        # a hostile entity in the line of fire: turn to face it, if that is safe (for a while: an aim that never lines
        # up, e.g. one turning into a turret's shots, gives way to the goal for as long)
        # turn to aim at what it hunts and at what moves at any range, else (turrets, nests) only when close: one in
        # range, but not in the way, isn't worth the detour
        hunting = any(ent.alive and ent.hostile and ent.covers(goal) for ent in map.entities)
        reach = None if hunting else self.DEFENCE
        aim = self._aim(snake, map, reach) if self._aiming < self.AIM_PATIENCE else None
        self._aiming = self._aiming + 1 if self._aiming < 2 * self.AIM_PATIENCE else 0
        if aim is not None:
            wanted = max(-1.0, min(1.0, aim[0] / snake.turn_speed))
            for steering in sorted(safe, key=lambda steering: abs(steering - wanted)):
                if self._escape(snake, map, *arcs[steering][1:3], arcs[steering][4]) == self.ESCAPE:
                    self.mode = "aim"
                    return steering
        if self._aiming < self.AIM_PATIENCE:
            self._aiming = 0  # not aiming: patience restored

        # turning circle: a target inside the circle on the side the snake turns to can't be reached by turning on, only
        # by straightening out first; without this the bot orbits the target until it bites its tail
        full_turn = snake.effective_speed / math.radians(snake.turn_speed)  # radius at full steering

        def distance(steering: float) -> float:
            """Way (px) left to the target from where the arc ends, plus ORBIT_PENALTY when it keeps circling; an arc
            passing over the target wins, the sooner the better."""
            _, pos, orient, reached, _ = arcs[steering]
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
        vacate = self._vacate(snake, map) if len(snake) >= self.LONG else None
        for steering in sorted(safe, key=distance):
            escapes[steering] = self._escape(snake, map, *arcs[steering][1:3], arcs[steering][4])
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

    def _aim(self, snake: "Snake", map: "Map", reach: float | None = None) -> tuple[float, float] | None:
        """(degrees to turn, degrees of tolerance) towards the nearest hostile entity in the weapon's range with no wall
        in between, or None."""
        weapon = snake.weapon
        if weapon is None or weapon.ammo <= 0 or getattr(weapon, "DROPS", False):
            return None
        head, best = snake.head.pos, None
        pierces = getattr(weapon, "PIERCE", False)
        for ent in map.entities:
            if not (ent.alive and ent.hostile and ent.exposed) or (ent.armored and not pierces):  # can't be hurt
                continue
            to_ent = ent.pos + Vec2(ent.w / 2, ent.h / 2) - head
            distance = to_ent.length()
            if not 0 < distance <= getattr(weapon, "range", 100) or (best and distance >= best[0]):
                continue
            if reach is not None and distance > reach and not hasattr(ent, "state"):  # standing still: no hurry
                continue
            if not map.clear_line(head, head + to_ent):
                continue
            turn = (pyxel.atan2(to_ent.y, to_ent.x) - snake.orient + 180) % 360 - 180
            # one behind (chasing the tail) can't be faced in time, unless it holds still (or never moves: no state)
            if abs(turn) > self.AIM_AHEAD and getattr(ent, "state", "rest") not in ("rest", "asleep"):
                continue
            aim = self.AIM + getattr(weapon, "FAN", 0)  # a fan of shots hits more to the sides
            best = (distance, turn, max(aim, math.degrees(math.atan2(ent.w / 2, distance))))
        return None if best is None else best[1:]

    def fire(self, snake, map):
        """Shoot when the weapon is ready and the nearest hostile entity in range is about straight ahead; drop a mine
        when one is on the snake's trail, within TRAIL px of the tail."""
        if snake.weapon is None or not snake.weapon.ready:
            return False
        if getattr(snake.weapon, "PULLS", False):  # the Tractor: when a pickup is in its cone
            from snake_quest.weapons import TractorBeam

            return any(ent.alive and ent.pullable and TractorBeam.in_cone(snake, ent) for ent in map.entities)
        if getattr(snake.weapon, "DROPS", False):
            tail = snake.segs[-1].pos
            return any(
                ent.alive and ent.hostile and (ent.pos + Vec2(ent.w / 2, ent.h / 2) - tail).length() < self.TRAIL
                for ent in map.entities
            )
        aim = self._aim(snake, map)
        return aim is not None and abs(aim[0]) <= aim[1]

    def _cell(self, pos: Vec2) -> tuple[int, int]:
        return int(pos.x) // self.CELL, int(pos.y) // self.CELL

    def _wall(self, map: "Map", cell: tuple[int, int]) -> bool:
        if map is not self._walls_map or map.walls_version != self._walls_version:
            self._walls, self._walls_map, self._walls_version = {}, map, map.walls_version
        if cell not in self._walls:
            center = Vec2(cell[0] * self.CELL + self.CELL / 2, cell[1] * self.CELL + self.CELL / 2)
            # cached: only the walls that stay (the trail comes and goes); thorns are walls for finding the way, though
            # an arc may still cross them when there is no other
            self._walls[cell] = (map.check_on_wall(center) and map.tile_xy(center) not in map.trail) or (
                map.tile_at(center) == HAZARD_TILE
            )
        if map.trail and not self._walls[cell]:
            return map.tile_xy(Vec2(cell[0] * self.CELL, cell[1] * self.CELL)) in map.trail
        if map.closing and not self._walls[cell]:  # an airlock door about to shut: never in it then
            return map.tile_xy(Vec2(cell[0] * self.CELL, cell[1] * self.CELL)) in map.closing
        if map.walls_version and not self._walls[cell]:  # a cave-in's warning: never back into it
            return map.tile_at(Vec2(cell[0] * self.CELL, cell[1] * self.CELL)) == CRACK_TILE
        return self._walls[cell]

    def _field(self, snake: "Snake", map: "Map", goal: tuple[int, int]) -> dict[tuple[int, int], int]:
        """Steps (cells) from every reachable cell to the target cell, breadth first from the target. Walls block;
        a body cell blocks unless its last segment will have moved on by the time the head, going straight, could be
        there. A portal leads to the other one's centre."""
        vacate, head, speed = self._vacate(snake, map), snake.head.pos, snake.effective_speed

        near_threat = {
            (cx, cy)
            for c, r in self._threats + self._solids
            for cx in range(int(c.x - r) // self.CELL, int(c.x + r) // self.CELL + 1)
            for cy in range(int(c.y - r) // self.CELL, int(c.y + r) // self.CELL + 1)
            if (Vec2(cx * self.CELL + self.CELL / 2, cy * self.CELL + self.CELL / 2) - c).length() < r
        }

        right, bottom = map.cfg.width // self.CELL, (map.header + map.cfg.height) // self.CELL
        top = map.header // self.CELL

        def blocked(cell: tuple[int, int]) -> bool:
            if not (0 <= cell[0] < right and top <= cell[1] < bottom):  # outside the level: no walls, but no way
                return True
            if self._wall(map, cell) or cell in near_threat:
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

    def _vacate(self, snake: "Snake", map: Optional["Map"] = None) -> dict[tuple[int, int], float]:
        """For every CELL-sized cell the body covers, and the cells next to it: frames until its last segment has moved
        on (each frame the segments shift by one; while growing, the tail stays) and, in a level with a trail, until
        the trail it leaves there has crumbled. Counting the neighbours too keeps the bot out of gaps in its body that
        are too narrow to steer through."""
        vacate: dict[tuple[int, int], float] = {}
        n, grow = len(snake), max(snake.grow, 0)
        linger = map.trail_seconds * map.game.cfg.fps if map is not None else 0
        for index, seg in enumerate(snake.segs[1:], start=1):
            x, y = int(seg.pos.x) // self.CELL, int(seg.pos.y) // self.CELL
            frames = n - index + grow + linger
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

    def _escape(self, snake: "Snake", map: "Map", pos: Vec2, orient: int, heading: float | None = None) -> int:
        """Frames the best of a hard turn or a straight line survives from there (at most ESCAPE)."""
        best = 0
        for turn in self.ESCAPES:
            best = max(best, self._arc(snake, map, pos, orient, turn, self.ESCAPE, heading=heading)[0])
            if best == self.ESCAPE:
                break
        return best

    def _arc(
        self,
        snake: "Snake",
        map: "Map",
        pos: Vec2,
        orient: int,
        steering: float,
        frames: int,
        goal: Vec2 | None = None,
        heading: float | None = None,
    ):
        """Follow `steering` for `frames` (drifting on ice like the snake, see `drift`): (frames survived, end position,
        end orientation, first frame within REACH of `goal` or None, end heading)."""
        reached, heading = None, orient if heading is None else heading
        skip = max(self.BODY_SKIP, snake.neck(self.BODY_SKIP))  # segments are ~1.3 px apart, closer while slowed
        speed, body = snake.effective_speed, snake.segs[skip::2]
        wells = getattr(map, "wells", None)
        for frame in range(1, frames + 1):
            orient = (orient + round(steering * snake.turn_speed)) % 360
            grip = map.grip_at(pos)
            heading = drift(heading, orient, grip)
            if wells:  # as the snake is pulled (see Snake.update)
                pull = map.pull(pos, heading)
                orient, heading = (orient + pull) % 360, (heading + pull) % 360
            pos = Vec2(pos.x + speed * pyxel.cos(heading), pos.y + speed * pyxel.sin(heading))
            p, q = collision_points(pos, heading, snake.size)
            near_body = frame % 2 == 0 and any((pos - seg.pos).length() < snake.size * 2 for seg in body)
            threatened = (
                any((pos - c).length() < r + frame * self.THREAT_GROWTH for c, r in self._threats)
                or any((pos - c).length() < r for c, r in self._solids)
                or any((pos - (shot + velocity * frame)).length() < self.DODGE for shot, velocity in self._shots)
            )
            if map.check_on_wall(p) or map.check_on_wall(q) or near_body or threatened:
                return frame - 1, pos, orient, reached, heading
            if reached is None and goal is not None and (goal - pos).length() < self.REACH:
                reached = frame
            partner = map.portals.get(map.tile_xy(pos))
            if partner is not None and partner != map.tile_xy(snake.head.pos):  # through the portal, as in the game
                pos = map.tile_center(partner)
        return frames, pos, orient, reached, heading


class RivalController(PathController):
    """The bot behind a rival snake (Ouroboros): a PathController whose foe is the player's snake, `prey` (set by its
    owner every frame): it aims and fires at its head, and keeps away from its body."""

    def __init__(self, target: Callable[["Snake", "Map"], Vec2 | None]):
        super().__init__(target)
        self.prey: Snake | None = None

    def threats(self, snake, map):
        if self.prey is None:
            return []
        return [(seg.pos, self.BODY) for seg in self.prey.segs[::2]]

    def _aim(self, snake, map, reach=None):
        """(degrees to turn, tolerance) towards the prey's head when it is in range and in sight, else None."""
        weapon = snake.weapon
        if self.prey is None or weapon is None or weapon.ammo <= 0:
            return None
        head, to_prey = snake.head.pos, self.prey.head.pos - snake.head.pos
        distance = to_prey.length()
        if not 0 < distance <= getattr(weapon, "range", 100) or not map.clear_line(head, self.prey.head.pos):
            return None
        turn = (pyxel.atan2(to_prey.y, to_prey.x) - snake.orient + 180) % 360 - 180
        if abs(turn) > self.AIM_AHEAD:
            return None
        return turn, self.AIM + getattr(weapon, "FAN", 0)


def nearest(
    *classes: type, clearance: int = 1, wary: float = 0, exclude: tuple[type, ...] = ()
) -> Callable[["Snake", "Map"], Vec2 | None]:
    """Target for a ChaseController or PathController: the centre of the nearest live entity of these classes (but not
    of the `exclude` ones, e.g. subclasses). Entities
    with a wall within `clearance` tiles (e.g. in a corner, hard to leave again) or within `wary` px of a hostile entity
    bots avoid (e.g. a pickup next to a turret) are only chosen when there is nothing else."""

    def open_around(map: "Map", pos: Vec2) -> bool:
        reach = range(-clearance, clearance + 1)
        return not any(map.check_on_wall(Vec2(pos.x + dx * 8, pos.y + dy * 8)) for dx in reach for dy in reach)

    def target(snake: "Snake", map: "Map") -> Vec2 | None:
        centres = [
            ent.pos + Vec2(ent.w / 2, ent.h / 2)
            for ent in map.entities
            if ent.alive and isinstance(ent, classes) and not isinstance(ent, exclude)
        ]
        foes = [ent.pos + Vec2(ent.w / 2, ent.h / 2) for ent in map.entities if ent.alive and ent.hostile and ent.avoid]
        safe = [
            pos
            for pos in centres
            if open_around(map, pos) and not any((pos - foe).length() < wary for foe in foes if wary)
        ]
        return min(safe or centres, key=lambda pos: (pos - snake.head.pos).length(), default=None)

    return target
