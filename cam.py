from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from main import Game
    from map import Map
from snake import Snake, Vec2


CAM_CENTER_SIZE = 30


class Cam:
    def __init__(self, snake: 'Snake', map: 'Map', game: 'Game'):
        self.snake: 'Snake' = snake
        self.map: 'Map' = map
        self.game: 'Game' = game
        self.offset: Vec2 = Vec2(0, 0)
        if self.width < 2 * CAM_CENTER_SIZE or self.height < 2 * CAM_CENTER_SIZE:
            raise RuntimeError('CAM_CENTER_SIZE too large.')

    @property
    def height(self):
        return self.game.cfg.area.h

    @property
    def width(self):
        return self.game.cfg.width

    @property
    def header_offset(self):
        return self.game.cfg.header.h

    @property
    def map_height(self):
        return self.map.cfg.height

    @property
    def map_width(self):
        return self.map.cfg.width

    def update(self):
        # set default such that snake head is at the center
        self.offset.x = self.width / 2 - self.snake.head.pos.x
        self.offset.y = self.height / 2 - (self.snake.head.pos.y - self.header_offset)
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
