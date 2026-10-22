"""Level timers (the `timers` section of a level file): call something after a while, once or again and again."""

import datetime
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake


class Timer:
    """Calls `callback(map=, snake=)` once `duration` of game time has passed, then every `frequency` (None: only once),
    at most `fire_n` times (0: no limit). It is done once `alive` is False; `enabled` pauses it."""

    def __init__(
        self,
        duration: datetime.timedelta,
        callback: Callable,
        frequency: datetime.timedelta | None = None,
        fire_n: int = 0,
    ):
        self._measured = datetime.timedelta(0)
        self.duration = duration
        self.callback = callback
        self.frequency = frequency
        self.fire_n = fire_n
        self._fired = 0
        self.enabled = True
        self.alive = True

    def update(self, map: "Map", snake: "Snake"):
        """Advance by the frame's game time (`map.game.dt`) and fire when due."""
        if self.enabled and self.alive:
            self._measured += map.game.dt
            if self._measured > self.duration:
                # reset timer
                self._measured -= self.duration
                if self.frequency is not None and (self.fire_n == 0 or self._fired < self.fire_n):
                    self.duration = self.frequency
                else:
                    self.alive = False
                # fire
                self.callback(map=map, snake=snake)
                self._fired += 1
