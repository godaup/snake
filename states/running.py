from typing import Optional, TYPE_CHECKING

from .abstract import GameStateHandler
from states import StateID

import pyxel
from map import Map
from snake import Snake, Vec2

if TYPE_CHECKING:
    from main import Game

COL_SCORE = 6
COL_SCORE_BACKGROUND = 5

TURN_SPEED = 9

class RunningStateHandler(GameStateHandler):

    def __init__(self, game: 'Game'):
        super().__init__(game=game)
        self.map = Map(level=game.level_counter)
        self.snake = Snake(pos=self.map.pos, orient=45, size=5, speed=3)

    @staticmethod
    def is_visible() -> bool:
        return False

    def get_music(self) -> Optional[int]:
        return 0

    def update(self) -> None:
        if pyxel.btn(pyxel.KEY_P):
            self.game.change_state(state=StateID.PAUSE)
        if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT):
            self.snake.turn(-TURN_SPEED)
        elif pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT):
            self.snake.turn(TURN_SPEED)
        self.snake.update(self.game.dt)
        if self.snake.self_intersect():
            self.game.change_state(state=StateID.DEATH)

    def draw(self) -> None:
        self.map.draw()
        self.snake.draw()
        pyxel.rect(0, 0, self.game.cfg.width, pyxel.FONT_HEIGHT, self.game.background)
        pyxel.text(1, 1, f"{self.game.score:04}", COL_SCORE)
