from typing import TYPE_CHECKING

import pyxel

if TYPE_CHECKING:
    from main import Game
    from map import Map
from snake import Snake
from utils import Vec2

CAM_CENTER_SIZE = 30


class Cam:
    def __init__(self, snake: 'Snake', map: 'Map', game: 'Game'):
        self.snake: 'Snake' = snake
        self.map: 'Map' = map
        self.game: 'Game' = game
        self.offset: Vec2 = Vec2(0, 0)

    def update(self):
        # set default such that snake head is at the center
        self.offset.x = self.map.cfg.width / 2 - self.snake.head.pos.x
        self.offset.y = self.map.cfg.height / 2 - (self.snake.head.pos.y - self.game.cfg.header.h)
        # now we may need to modify based on snake position
        # top border
        self.offset.y = min(CAM_CENTER_SIZE, self.offset.y)
        # left border
        self.offset.x = min(CAM_CENTER_SIZE, self.offset.x)
        # bottom border
        self.offset.y = max(-CAM_CENTER_SIZE, self.offset.y)
        # right border
        self.offset.x = max(-CAM_CENTER_SIZE, self.offset.x)

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
