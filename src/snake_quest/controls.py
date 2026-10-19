"""Input layer: what steers a snake. The player uses keyboard or gamepad; tests, bots and (later) the rival snake use
other controllers through the same interface, so `Snake` never reads input itself."""

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
    """A bot that takes the shortest way through the level (walking distances, portals included) to
    `target(snake, map)`. Every frame it tries a fan of steering values, each held for HORIZON frames, and drops the
    arcs that run into a wall or its own body, or that end where no hard turn or straight line gets it out again
    (ESCAPE frames). Of the rest it takes the one ending closest to the target along the way."""

    STEERING = (-1.0, -0.5, 0.0, 0.5, 1.0)
    ESCAPES = (-1.0, 0.0, 1.0)
    HORIZON = 16  # frames looked ahead
    ESCAPE = 12  # frames an arc's end must leave room for
    BODY_SKIP = 6  # segments next to the head that can't be bitten

    def __init__(self, target: Callable[["Snake", "Map"], Vec2 | None]):
        self.target = target
        self._goal_tile: tuple[int, int] | None = None
        self._distance: dict[tuple[int, int], int] = {}

    def steer(self, snake, map):
        goal = self.target(snake, map)
        if goal is None:
            return 0.0
        goal_tile = map.tile_xy(goal)
        if goal_tile != self._goal_tile:
            self._goal_tile, self._distance = goal_tile, map.walking_distances(goal)
        return min(self.STEERING, key=lambda steering: self._cost(snake, map, goal, steering))

    def _arc(self, snake: "Snake", map: "Map", pos: Vec2, orient: int, steering: float, frames: int):
        """Follow `steering` for `frames`: (frames survived, end position, end orientation)."""
        speed, body = snake.effective_speed, snake.segs[self.BODY_SKIP :: 2]  # segments are ~1.3 px apart
        for frame in range(1, frames + 1):
            orient = (orient + round(steering * snake.turn_speed)) % 360
            pos = Vec2(pos.x + speed * pyxel.cos(orient), pos.y + speed * pyxel.sin(orient))
            p, q = collision_points(pos, orient, snake.size)
            near_body = frame % 2 == 0 and any((pos - seg.pos).length() < snake.size * 2 for seg in body)
            if map.check_on_wall(p) or map.check_on_wall(q) or near_body:
                return frame - 1, pos, orient
        return frames, pos, orient

    def _cost(self, snake: "Snake", map: "Map", goal: Vec2, steering: float) -> float:
        """Unsafe arcs cost more the sooner they crash, safe ones the walking distance (in px) left from their end."""
        survived, pos, orient = self._arc(snake, map, snake.head.pos, snake.orient, steering, self.HORIZON)
        if survived < self.HORIZON:
            return 1e6 * (2 * self.HORIZON - survived)
        escape = max(self._arc(snake, map, pos, orient, turn, self.ESCAPE)[0] for turn in self.ESCAPES)
        if escape < self.ESCAPE:
            return 1e6 * (self.ESCAPE - escape)
        steps = self._distance.get(map.tile_xy(pos), len(self._distance))
        return steps * 8 + (goal - pos).length()


def nearest(*classes: type) -> Callable[["Snake", "Map"], Vec2 | None]:
    """Target for a ChaseController or PathController: the centre of the nearest live entity of these classes."""

    def target(snake: "Snake", map: "Map") -> Vec2 | None:
        centres = [
            ent.pos + Vec2(ent.w / 2, ent.h / 2) for ent in map.entities if ent.alive and isinstance(ent, classes)
        ]
        return min(centres, key=lambda pos: (pos - snake.head.pos).length(), default=None)

    return target
