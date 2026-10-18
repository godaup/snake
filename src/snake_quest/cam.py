from typing import TYPE_CHECKING

import pyxel

if TYPE_CHECKING:
    from snake_quest.game import Game
    from snake_quest.map import Map
from snake_quest.snake import Snake
from snake_quest.utils import Vec2

CAM_CENTER_SIZE_X = 140
CAM_CENTER_SIZE_Y = 80


class Cam:
    def __init__(self, snake: "Snake", map: "Map", game: "Game"):
        self.snake: Snake = snake
        self.map: Map = map
        self.game: Game = game
        self.offset: Vec2 = Vec2(0, 0)

    def update(self):
        left_border = CAM_CENTER_SIZE_X
        right_border = self.map.cfg.width - CAM_CENTER_SIZE_X
        top_border = CAM_CENTER_SIZE_Y + self.game.cfg.header.h
        bottom_border = self.map.cfg.height + self.game.cfg.header.h - CAM_CENTER_SIZE_Y
        perspective_pos_x = min(max(left_border, int(self.snake.head.pos.x)), right_border)
        perspective_pos_y = min(max(top_border, int(self.snake.head.pos.y)), bottom_border)
        # set default such that snake head is at the center
        self.offset.x = self.game.cfg.width / 2 - perspective_pos_x
        self.offset.y = self.game.cfg.area.h / 2 - perspective_pos_y + self.game.cfg.header.h

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
