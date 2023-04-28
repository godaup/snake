from abstract import GameState
import pyxel

from main import StateID

TEXT_DEATH = ["GAME OVER", "(Q)UIT", "(R)ESTART"]
COL_TEXT_DEATH = 0
HEIGHT_DEATH = 5
COL_DEATH = 8


class DeathState(GameState):

    def update(self) -> None:
        pass

    @staticmethod
    def is_visible() -> bool:
        return False

    def draw(self) -> None:
        """Draw a blank screen with some text."""

        pyxel.cls(col=COL_DEATH)
        display_text = TEXT_DEATH[:]
        display_text.insert(1, f"{self.game.score:04}")
        for i, text in enumerate(display_text):
            y_offset = (pyxel.FONT_HEIGHT + 2) * i
            text_x = self.game.center_text(text, self.game.cfg.width)
            pyxel.text(text_x, HEIGHT_DEATH + y_offset, text, COL_TEXT_DEATH)

    def reset(self):
        """reset variables, restart game"""
        self.game.score = 0
        self.game.level_counter = 1
        self.game.change_state(state=StateID.RUNNING)
