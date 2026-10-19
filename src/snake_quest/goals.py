"""Win conditions of a level, built from the `goal` section of its YAML file. All goals must be met."""

import datetime
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from snake_quest.entity import ENTITY_NAMES
from snake_quest.tiles import EXIT_TILE

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

    def done(self, map, snake):
        return map.tile_at(snake.head.pos) == self.value

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


GOALS: dict[str, type[Goal]] = {
    cls.key: cls for cls in (ScoreGoal, LengthGoal, ExitGoal, SurviveGoal, DefeatGoal, HoldLengthGoal, CollectAllGoal)
}


def load_goals(cfg, map: "Map") -> list[Goal]:
    if not cfg:
        raise ValueError("a level needs at least one goal, otherwise it is won on the first frame")
    unknown = set(cfg) - set(GOALS)
    if unknown:
        raise ValueError(f"unknown goal types {sorted(unknown)}, known: {sorted(GOALS)}")
    return [GOALS[key](value, map) for key, value in cfg.items()]
