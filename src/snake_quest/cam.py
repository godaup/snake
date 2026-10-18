from typing import TYPE_CHECKING

import pyxel

if TYPE_CHECKING:
    from snake_quest.game import Game
    from snake_quest.map import Map
from snake_quest.snake import Snake
from snake_quest.utils import Vec2


def _follow(screen: float, world: float, target: float) -> float:
    """Offset that centres `target` on a screen axis of length `screen`, without showing anything beyond the map
    (length `world`); a map smaller than the screen is centred."""
    if world <= screen:
        return (screen - world) / 2
    return min(0.0, max(screen - world, screen / 2 - target))


class Cam:
    def __init__(self, snake: "Snake", map: "Map", game: "Game"):
        self.snake: Snake = snake
        self.map: Map = map
        self.game: Game = game
        self.offset: Vec2 = Vec2(0, 0)

    def update(self):
        """Keep the snake head centred, clamped to the map edges. World y includes the header, so the vertical axis
        is computed in map coordinates (head y minus header)."""
        header = self.game.cfg.header.h
        head = self.snake.head.pos
        self.offset.x = _follow(self.game.cfg.width, self.map.cfg.width, head.x)
        self.offset.y = _follow(self.game.cfg.area.h, self.map.cfg.height, head.y - header)

    def draw(self):
        self.map.draw(self.offset)
        self.snake.draw(self.offset)
        if self.game.cfg.debug:
            # draw collision points
            p, q = self.snake.get_collision_points()
            pyxel.pset(x=p.x + self.offset.x, y=p.y + self.offset.y, col=12)
            pyxel.pset(x=q.x + self.offset.x, y=q.y + self.offset.y, col=12)
            # draw snake center
            pyxel.pset(x=self.snake.head.pos.x + self.offset.x, y=self.snake.head.pos.y + self.offset.y, col=15)
