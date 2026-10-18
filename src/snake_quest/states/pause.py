from typing import TYPE_CHECKING

import pyxel

from snake_quest.states import StateID
from snake_quest.states.abstract import GameStateHandler
from snake_quest.widget import WIDGET_MARGIN, Widget

if TYPE_CHECKING:
    from snake_quest.game import Game


class PauseStateHandler(GameStateHandler):
    def __init__(self, game: "Game"):
        super().__init__(game=game)
        text = "PAUSED  (P) RESUME  (ESC) MENU"
        self.wdg = Widget(
            x=self.center_text(text=text) - WIDGET_MARGIN,
            y=(self.game.cfg.area.h / 2 + self.game.cfg.header.h) - WIDGET_MARGIN,
            w=pyxel.FONT_WIDTH * len(text) + 2 * WIDGET_MARGIN,
            h=pyxel.FONT_HEIGHT + 2 * WIDGET_MARGIN,
            text=[text],
            bg=3,
        )

    @staticmethod
    def is_visible() -> bool:
        return True

    def update(self) -> None:
        if pyxel.btnp(pyxel.KEY_P) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_START):
            self.game.change_state(state=StateID.RUNNING)
        elif pyxel.btnp(pyxel.KEY_ESCAPE) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_B):
            self.game.change_state(state=StateID.MENU)

    def draw(self) -> None:
        self.wdg.draw()
