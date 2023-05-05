from .abstract import GameStateHandler
import pyxel

from states import StateID

COL_TEXT_DEATH = 0
COL_DEATH = 8


class DeathStateHandler(GameStateHandler):

    def update(self) -> None:
        if pyxel.btnp(pyxel.KEY_R) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_A):
            self.game.restart()
        if pyxel.btn(pyxel.KEY_Q):
            pyxel.quit()

    @staticmethod
    def is_visible() -> bool:
        return False

    def draw(self) -> None:
        """Draw a blank screen with some text."""

        pyxel.cls(col=COL_DEATH)
        display_text = ["GAME OVER", f"{self.game.score:04}", "(Q)UIT", "(R)ESTART"]
        for i, text in enumerate(display_text):
            y_offset = (pyxel.FONT_HEIGHT + 2) * (i - len(display_text)//2)
            text_x = self.center_text(text)
            pyxel.text(text_x, self.game.cfg.height // 2 + y_offset, text, COL_TEXT_DEATH)
