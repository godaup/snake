from typing import TYPE_CHECKING

import pyxel

from states import StateID
from states.abstract import GameStateHandler
from widget import WIDGET_MARGIN, Button, ImgInfo

if TYPE_CHECKING:
    from main import Game


class MenuStateHandler(GameStateHandler):
    def __init__(self, game: "Game"):
        super().__init__(game=game)
        text = "(P)lay"
        self.play_btn = Button(
            x=self.center_text(text=text) - WIDGET_MARGIN,
            y=(self.game.cfg.area.h / 2 + self.game.cfg.header.h) - WIDGET_MARGIN,
            text=[text],
            on_click=self.play_callback,
            img=ImgInfo(nr=0, u=0, v=48, h=8, w=8, collkey=0),
            hotkey=pyxel.KEY_P,
        )

    @staticmethod
    def is_visible() -> bool:
        return True

    def update(self) -> None:
        self.play_btn.update()

    def draw(self) -> None:
        pyxel.cls(col=self.game.cfg.area.bg)
        self.play_btn.draw()

    def play_callback(self):
        self.game.change_state(StateID.RUNNING)
