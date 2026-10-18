from typing import TYPE_CHECKING

import pyxel

from snake_quest.cam import Cam
from snake_quest.hud import Hud
from snake_quest.map import Map
from snake_quest.palettes import palette
from snake_quest.snake import Snake
from snake_quest.states import StateID
from snake_quest.states.abstract import GameStateHandler

if TYPE_CHECKING:
    from snake_quest.game import Game

TURN_SPEED = 9
SNAKE_SIZE = 2


class RunningStateHandler(GameStateHandler):
    def __init__(self, game: "Game"):
        super().__init__(game=game)
        self.map = Map(level=game.campaign.level(game.level_counter), game=self.game)
        self.snake = Snake(pos=self.map.start, orient=45, size=SNAKE_SIZE, colors=palette(game.profile.palette))
        self.cam = Cam(snake=self.snake, map=self.map, game=self.game)
        self.hud = Hud(game=self.game, level_map=self.map, snake=self.snake)
        self.countdown = True

    @staticmethod
    def is_visible() -> bool:
        return False

    def get_music(self) -> int | None:
        return 0

    def update(self) -> None:
        # pause
        if pyxel.btnp(pyxel.KEY_P) or pyxel.btnp(pyxel.KEY_ESCAPE) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_START):
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
        self.hud.draw()
