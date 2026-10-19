"""Input layer: what steers a snake. The player uses keyboard or gamepad; tests, bots and (later) the rival snake use
other controllers through the same interface, so `Snake` never reads input itself."""

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Optional

import pyxel

from snake_quest.utils import Vec2

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
