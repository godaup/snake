"""Win conditions of a level, built from the `goal` section of its YAML file. All goals must be met."""

import datetime
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from snake_quest.entity import ENTITY_NAMES

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


class ScoreGoal(Goal):
    """`score: N`: gain N points in this level."""

    key = "score"

    def __init__(self, value, map):
        super().__init__(value, map)
        self.score_before = map.game.score

    def done(self, map, snake):
        return map.game.score - self.score_before >= self.value

    def describe(self):
        return f"Score {self.value} points"


class LengthGoal(Goal):
    """`length: N`: be at least N segments long."""

    key = "length"

    def done(self, map, snake):
        return len(snake) >= self.value

    def describe(self):
        return f"Grow to length {self.value}"


class ExitGoal(Goal):
    """`exit: [x, y]`: reach a tile showing sprite tile (x, y)."""

    key = "exit"

    def __init__(self, value, map):
        super().__init__(tuple(value), map)

    def done(self, map, snake):
        return map.tile_at(snake.head.pos) == self.value

    def describe(self):
        return "Find the exit"


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
        return f"Survive {self.value} seconds"


class DefeatGoal(Goal):
    """`defeat: N`: kill N entities (eating does not count)."""

    key = "defeat"

    def done(self, map, snake):
        return map.defeated >= self.value

    def describe(self):
        return f"Defeat {self.value} enemies"


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
        return f"Stay {self.value['length']} long for {self.value['seconds']} seconds"


class CollectAllGoal(Goal):
    """`collect_all: <entity name>`: no entity of that kind is left on the map."""

    key = "collect_all"

    def __init__(self, value, map):
        super().__init__(value, map)
        self.entity_cls = ENTITY_NAMES[value]

    def done(self, map, snake):
        return not any(isinstance(ent, self.entity_cls) and ent.alive for ent in map.entities)

    def describe(self):
        return f"Collect every {self.value}"


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
