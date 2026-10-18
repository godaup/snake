import datetime
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from snake_quest.map import Map
    from snake_quest.snake import Snake


class Timer:
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
