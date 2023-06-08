from typing import Optional, TYPE_CHECKING

import pyxel

from cam import Cam
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
SNAKE_SIZE = 2


class RunningStateHandler(GameStateHandler):

    def __init__(self, game: 'Game'):
        super().__init__(game=game)
        self.map = Map(level=game.level_counter, game=self.game)
        self.snake = Snake(pos=self.map.start, orient=45, size=SNAKE_SIZE)
        self.cam = Cam(snake=self.snake, map=self.map, game=self.game)
        self.score_board = Widget(x=0, y=0, w=len(self.get_score_text()) * pyxel.FONT_WIDTH + 2 * WIDGET_MARGIN, bg=10,
                                  text_col=12)
        self.header.add_sub_widget(self.score_board)
        self.level_widget = Widget(x=(self.game.cfg.width + len(self.get_level_text())) / 2, y=0,
                                   w=len(self.get_level_text()) * pyxel.FONT_WIDTH + 2 * WIDGET_MARGIN, bg=10,
                                   text_col=12)
        self.header.add_sub_widget(self.level_widget)
        self.countdown = True

    def get_score_text(self):
        return f"Score: {self.game.score:04}"

    def get_level_text(self):
        return f"Level: {self.game.level_counter}"
        #p = self.snake.get_collision_points()[0]
        #return f"{pyxel.tilemap(0).pget(pyxel.mouse_x / 8, (pyxel.mouse_y - self.header.h) / 8)}"

    @staticmethod
    def is_visible() -> bool:
        return False

    def get_music(self) -> Optional[int]:
        return 0

    def update(self) -> None:
        # pause
        if pyxel.btnp(pyxel.KEY_P):
            self.game.change_state(state=StateID.PAUSE)
        # turn
        if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_LEFT):
            self.snake.turn(-TURN_SPEED)
        elif pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT):
            self.snake.turn(TURN_SPEED)
        # update snake
        self.snake.update(dt=self.game.dt, map=self.map)
        if self.snake.self_intersect():
            self.game.change_state(state=StateID.DEATH)
        # update widgets
        self.score_board.text = [self.get_score_text()]
        self.level_widget.text = [self.get_level_text()]
        # calc offset
        self.cam.update()
        # update entities and timers and projectiles
        self.map.update(snake=self.snake)
        # check wall collisions
        p, q = self.snake.get_collision_points()
        if self.map.check_on_wall(p) or self.map.check_on_wall(q):
            self.game.change_state(state=StateID.DEATH)
        # check win
        if self.map.check_win(snake=self.snake):
            self.game.level_up()
        # after first frame is rendered, change into countdown mode once
        if self.countdown:
            self.countdown = False
            self.game.change_state(StateID.COUNTDOWN)

    def draw(self) -> None:
        pyxel.cls(self.game.cfg.area.bg)
        # draw game with offset
        self.cam.draw()
        self.header.draw()
        self.footer.draw()
