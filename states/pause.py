from .abstract import GameStateHandler
import pyxel
from states import StateID
from typing import TYPE_CHECKING
from widget import Widget, WIDGET_MARGIN

if TYPE_CHECKING:
    from main import Game


class PauseStateHandler(GameStateHandler):
    def __init__(self, game: 'Game'):
        super().__init__(game=game)
        text = "(P)aused"
        self.wdg = Widget(x=self.center_text(text=text) - WIDGET_MARGIN,
                          y=(self.game.cfg.area.h / 2 + self.game.cfg.header.h) - WIDGET_MARGIN,
                          w=pyxel.FONT_WIDTH * len(text) + 2 * WIDGET_MARGIN,
                          h=pyxel.FONT_HEIGHT + 2 * WIDGET_MARGIN,
                          text=[text], bg=3)

    @staticmethod
    def is_visible() -> bool:
        return False

    def update(self) -> None:

        if pyxel.btnp(pyxel.KEY_P):
            self.game.change_state(state=StateID.RUNNING)

    def draw(self) -> None:
        self.wdg.draw()


# TODO look up button buffering in examples to avoid flickering
