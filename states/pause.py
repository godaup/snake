from .abstract import GameStateHandler
import pyxel
from states import StateID


class PauseStateHandler(GameStateHandler):

    @staticmethod
    def is_visible() -> bool:
        return False

    def update(self) -> None:

        if pyxel.btn(pyxel.KEY_P):
            self.game.change_state(state=StateID.RUNNING)

    def draw(self) -> None:
        pass
