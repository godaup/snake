"""Win conditions of a level, built from the `goal` section of its YAML file. All goals must be met."""

import datetime
import heapq
import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

import pyxel

from snake_quest.entity import ENTITY_NAMES
from snake_quest.tiles import CRACK_TILE, EXIT_TILE, RUBBLE_TILE, WALL_TILES
from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake


class Goal(ABC):
    key: ClassVar[str]

    def __init__(self, value, map: "Map"):
        self.value = value

    def update(self, map: "Map", snake: "Snake", dt: datetime.timedelta) -> None:  # noqa: B027 (optional hook)
        """Called every running frame, for goals that track time."""

    @abstractmethod
    def done(self, map: "Map", snake: "Snake") -> bool: ...

    @abstractmethod
    def describe(self) -> str:
        """Short text for the level intro / HUD."""

    @abstractmethod
    def status(self, map: "Map", snake: "Snake") -> str:
        """Current state in a few characters for the footer, e.g. 'SCORE 23/100'."""

    def progress(self, map: "Map", snake: "Snake") -> float | None:
        """How far along the goal is, 0..1, or None when there is nothing to measure (e.g. finding the exit)."""
        return None


class ScoreGoal(Goal):
    """`score: N`: gain N points in this level."""

    key = "score"

    def __init__(self, value, map):
        super().__init__(value, map)
        self.score_before = map.game.score

    def done(self, map, snake):
        return map.game.score - self.score_before >= self.value

    def describe(self):
        return f"Score {_count(self.value, 'point')}"

    def status(self, map, snake):
        return f"SCORE {max(map.game.score - self.score_before, 0)}/{self.value}"

    def progress(self, map, snake):
        return _fraction(map.game.score - self.score_before, self.value)


class LengthGoal(Goal):
    """`length: N`: be at least N segments long."""

    key = "length"

    def done(self, map, snake):
        return len(snake) >= self.value

    def describe(self):
        return f"Grow to length {self.value}"

    def status(self, map, snake):
        return f"LENGTH {len(snake)}/{self.value}"

    def progress(self, map, snake):
        return _fraction(len(snake), self.value)


class ExitGoal(Goal):
    """`exit: true`: reach an exit tile (EXIT_TILE); `exit: [x, y]`: reach a tile showing sprite tile (x, y)."""

    key = "exit"

    def __init__(self, value, map):
        super().__init__(EXIT_TILE if value is True else tuple(value), map)
        self._tiles: list[tuple[int, int]] | None = None

    def done(self, map, snake):
        return map.tile_at(snake.head.pos) == self.value

    def tiles(self, map: "Map") -> list[tuple[int, int]]:
        """Tile coordinates of the exits (looked up once), e.g. for bots."""
        if self._tiles is None:
            tilemap = pyxel.tilemaps[map.tm]
            width, height = map.cfg.width // 8, map.cfg.height // 8
            self._tiles = [(x, y) for y in range(height) for x in range(width) if tilemap.pget(x, y) == self.value]
        return self._tiles

    def describe(self):
        return "Find the exit"

    def status(self, map, snake):
        return "FIND THE EXIT"


class SurviveGoal(Goal):
    """`survive: seconds`: stay alive that long."""

    key = "survive"

    def __init__(self, value, map):
        super().__init__(value, map)
        self.elapsed = datetime.timedelta(0)

    def update(self, map, snake, dt):
        self.elapsed += dt

    def done(self, map, snake):
        return self.elapsed >= datetime.timedelta(seconds=self.value)

    def describe(self):
        return f"Survive {_count(self.value, 'second')}"

    def status(self, map, snake):
        left = max(self.value - self.elapsed.total_seconds(), 0)
        return f"SURVIVE {left:.0f}s"

    def progress(self, map, snake):
        return _fraction(self.elapsed.total_seconds(), self.value)


class TimeLimitGoal(Goal):
    """`time_limit: seconds`: the other goals must be done within this time; when it runs out, the level is lost
    (`map.snake_killed`)."""

    key = "time_limit"

    def __init__(self, value, map):
        super().__init__(value, map)
        self.elapsed = datetime.timedelta(0)

    def left(self) -> float:
        return max(self.value - self.elapsed.total_seconds(), 0.0)

    def update(self, map, snake, dt):
        self.elapsed += dt
        if self.left() <= 0:
            map.snake_killed = True

    def done(self, map, snake):
        return self.left() > 0

    def describe(self):
        return f"Within {_count(round(self.value), 'second')}"

    def status(self, map, snake):
        minutes, seconds = divmod(math.ceil(self.left()), 60)
        return f"TIME {minutes}:{seconds:02}"

    def progress(self, map, snake):
        return _fraction(self.left(), self.value)


class CollapseGoal(Goal):
    """`collapse: {speed: px/s, start: s, warn: s}`: the cave comes down behind the snake. After `start` seconds a front
    moves out from the start at `speed` (along the ways through the cave, so side caverns and dead ends fill too): the
    floor it reaches turns to rubble, a wall for good, the last `warn` seconds before it cracked (dust falling). Caught
    by it, the snake's body is cut off there, and its head is the end. Always done: it is the pressure on the other
    goals (an exit), like a time limit. The ground trembles while it is near."""

    key = "collapse"
    NEAR = 96  # px: closer, the camera shakes (and harder within half of it)

    def __init__(self, value, map):
        super().__init__(value, map)
        self.speed, self.start, self.warn = float(value["speed"]), float(value["start"]), float(value["warn"])
        self.elapsed = 0.0
        # every tile the snake can reach, nearest first (px along the way from the start)
        self.along = self._distances(map)
        self.order = sorted(self.along, key=self.along.get)
        self.filled = 0  # tiles of `order` turned to rubble
        self.cracked = 0  # tiles of `order` cracked
        self.lead = float("inf")  # px between the front and the snake's head

    @staticmethod
    def _distances(map) -> dict[tuple[int, int], float]:
        """Px from the start to every reachable tile, moving straight or diagonally (diagonals only where both tiles
        beside the corner are open): about the length of the way the snake takes, so the front keeps its speed in
        bends too."""
        tilemap = pyxel.tilemaps[map.tm]
        width, height = map.cfg.width // 8, map.cfg.height // 8

        def open_(tile):
            return 0 <= tile[0] < width and 0 <= tile[1] < height and tilemap.pget(*tile) not in WALL_TILES

        start = map.tile_xy(map.start)
        along, queue = {start: 0.0}, [(0.0, start)]
        while queue:
            steps, (x, y) = heapq.heappop(queue)
            if steps > along[x, y]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                nxt = (x + dx, y + dy)
                if not open_(nxt) or (dx and dy and not (open_((x + dx, y)) and open_((x, y + dy)))):
                    continue
                cost = steps + (11.3 if dx and dy else 8.0)
                if cost < along.get(nxt, float("inf")):
                    along[nxt] = cost
                    heapq.heappush(queue, (cost, nxt))
        return along

    def front(self) -> float:
        """How far (px along the way) the cave has come down."""
        return max(0.0, (self.elapsed - self.start) * self.speed)

    def update(self, map, snake, dt):
        self.elapsed += dt.total_seconds()
        front = self.front()
        tilemap = pyxel.tilemaps[map.tm]
        while self.cracked < len(self.order) and self.along[self.order[self.cracked]] < front + self.speed * self.warn:
            tile = self.order[self.cracked]
            if tilemap.pget(*tile) not in WALL_TILES:
                tilemap.pset(*tile, CRACK_TILE)
            self.cracked += 1
        caught = False
        while self.filled < len(self.order) and self.along[self.order[self.filled]] < front:
            tile = self.order[self.filled]
            map.fill(tile, RUBBLE_TILE)
            for ent in map.entities:
                if ent.alive and map.tile_xy(ent.pos + Vec2(ent.w / 2, ent.h / 2)) == tile:
                    ent.alive = False  # buried
            self.filled += 1
            caught = True
        if caught:
            index = next((i for i, seg in enumerate(snake.segs) if map.check_on_wall(seg.pos)), None)
            if index == 0:
                map.snake_killed = True
            elif index is not None:
                snake.segs = snake.segs[:index]
                map.game.sm.effect("hurt")
        head = self.along.get(map.tile_xy(snake.head.pos))
        self.lead = head - front if head is not None and front > 0 else float("inf")
        map.shake = 2 if self.lead < self.NEAR / 2 else 1 if self.lead < self.NEAR else 0

    def done(self, map, snake):
        return True

    def describe(self):
        return "Outrun the cave-in"

    def status(self, map, snake):
        if self.front() <= 0:
            return f"CAVE-IN IN {math.ceil(self.start - self.elapsed)}s"
        lead = "-" if self.lead == float("inf") else str(max(0, int(self.lead // 8)))
        return f"CAVE-IN {lead}m BEHIND"

    def progress(self, map, snake):
        return None if self.lead == float("inf") else _fraction(self.lead, 4 * self.NEAR)


class DefeatGoal(Goal):
    """`defeat: N`: kill N entities (eating does not count)."""

    key = "defeat"

    def done(self, map, snake):
        return map.defeated >= self.value

    def describe(self):
        return f"Defeat {_count(self.value, 'enemy', 'enemies')}"

    def status(self, map, snake):
        return f"DEFEAT {map.defeated}/{self.value}"

    def progress(self, map, snake):
        return _fraction(map.defeated, self.value)


class HoldLengthGoal(Goal):
    """`hold_length: {length: N, seconds: T}`: stay at least N long for T seconds in a row."""

    key = "hold_length"

    def __init__(self, value, map):
        super().__init__(value, map)
        self.held = datetime.timedelta(0)

    def update(self, map, snake, dt):
        self.held = self.held + dt if len(snake) >= self.value["length"] else datetime.timedelta(0)

    def done(self, map, snake):
        return self.held >= datetime.timedelta(seconds=self.value["seconds"])

    def describe(self):
        return f"Stay {self.value['length']} long for {_count(self.value['seconds'], 'second')}"

    def status(self, map, snake):
        return f"HOLD {self.value['length']}+ {self.held.total_seconds():.0f}/{self.value['seconds']}s"

    def progress(self, map, snake):
        return _fraction(self.held.total_seconds(), self.value["seconds"])


class CollectAllGoal(Goal):
    """`collect_all: <entity name>`: no entity of that kind is left on the map."""

    key = "collect_all"

    def __init__(self, value, map):
        super().__init__(value, map)
        self.entity_cls = ENTITY_NAMES[value]
        self.seen: set = set()  # every matching entity so far, so later spawns count towards the total
        self.counts(map)

    def counts(self, map) -> tuple[int, int]:
        """(collected, total) so far."""
        alive = [ent for ent in map.entities if isinstance(ent, self.entity_cls) and ent.alive]
        self.seen.update(alive)
        return len(self.seen) - len(alive), len(self.seen)

    def remaining(self, map) -> int:
        collected, total = self.counts(map)
        return total - collected

    def done(self, map, snake):
        return self.remaining(map) == 0

    def describe(self):
        return f"Collect every {self.value}"

    def status(self, map, snake):
        collected, total = self.counts(map)
        return f"{self.value.upper()} {collected}/{total}"

    def progress(self, map, snake):
        return _fraction(*self.counts(map))


def _count(n, singular: str, plural: str | None = None) -> str:
    """'1 point', '3 points'."""
    return f"{n} {singular if n == 1 else plural or singular + 's'}"


def _fraction(value: float, target: float) -> float:
    return 1.0 if target <= 0 else min(max(value / target, 0.0), 1.0)


class DestroyAllGoal(CollectAllGoal):
    """`destroy_all: <entity name>`: like collect_all, for things that are shot rather than eaten (e.g. nests)."""

    key = "destroy_all"

    def describe(self):
        return f"Destroy every {self.value}"


class BossGoal(Goal):
    """`boss: defeated`: beat the level's boss (its `defeated()`); the footer shows its bar."""

    key = "boss"

    def done(self, map, snake):
        return map.boss is not None and map.boss.defeated(map)

    def describe(self):
        return "Defeat the boss"

    def status(self, map, snake):
        return "BOSS" if map.boss is None else f"BOSS {round(map.boss.bar(map, snake) * 100)}%"

    def progress(self, map, snake):
        return None if map.boss is None else 1 - map.boss.bar(map, snake)


GOALS: dict[str, type[Goal]] = {
    cls.key: cls
    for cls in (
        ScoreGoal,
        LengthGoal,
        ExitGoal,
        SurviveGoal,
        TimeLimitGoal,
        DefeatGoal,
        HoldLengthGoal,
        CollapseGoal,
        CollectAllGoal,
        DestroyAllGoal,
        BossGoal,
    )
}


def load_goals(cfg, map: "Map") -> list[Goal]:
    if not cfg:
        raise ValueError("a level needs at least one goal, otherwise it is won on the first frame")
    unknown = set(cfg) - set(GOALS)
    if unknown:
        raise ValueError(f"unknown goal types {sorted(unknown)}, known: {sorted(GOALS)}")
    return [GOALS[key](value, map) for key, value in cfg.items()]
