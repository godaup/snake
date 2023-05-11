from typing import Optional, TYPE_CHECKING

import pyxel

from map import Map
from snake import Snake
from states import StateID
from widget import Widget, WIDGET_MARGIN
from .abstract import GameStateHandler

if TYPE_CHECKING:
    from main import Game

COL_SCORE = 6
COL_SCORE_BACKGROUND = 5

TURN_SPEED = 9
MOVE_SPEED = 1.3
SNAKE_SIZE = 2


class RunningStateHandler(GameStateHandler):

    def __init__(self, game: 'Game'):
        super().__init__(game=game)
        self.map = Map(level=game.level_counter, game=self.game)
        self.snake = Snake(pos=self.map.pos, orient=45, size=SNAKE_SIZE, speed=MOVE_SPEED)
        self.score_board = Widget(x=0, y=0, w=len(self.get_score_text()) * pyxel.FONT_WIDTH + 2 * WIDGET_MARGIN, bg=10,
                                  text_col=12)
        self.header.add_sub_widget(self.score_board)
        self.level_widget = Widget(x=(self.game.cfg.width + len(self.get_level_text())) / 2, y=0,
                                   w=len(self.get_level_text()) * pyxel.FONT_WIDTH + 2 * WIDGET_MARGIN, bg=10,
                                   text_col=12)
        self.header.add_sub_widget(self.level_widget)

    def get_score_text(self):
        return f"Score: {self.game.score:04}"

    def get_level_text(self):
        return f"Level: {self.game.level_counter}"

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

        self.score_board.text = [self.get_score_text()]
        self.level_widget.text = [self.get_level_text()]

    def draw(self) -> None:
        self.header.draw()
        self.footer.draw()
        self.map.draw()
        self.snake.draw()
