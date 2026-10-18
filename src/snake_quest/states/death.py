import pyxel

from snake_quest.states.abstract import GameStateHandler
from snake_quest.widget import TEXT_LINE_SPACING, WIDGET_MARGIN, Widget

COL_TEXT_DEATH = 0
COL_DEATH = 8


class DeathStateHandler(GameStateHandler):
    def __init__(self, game):
        super().__init__(game=game)
        text = ["GAME OVER", "(Q)UIT", "(R)ESTART"]
        self.wdg = Widget(
            x=min([self.center_text(line) for line in text]) - WIDGET_MARGIN,
            y=self.game.cfg.area.h // 2
            + self.game.cfg.header.h
            + (pyxel.FONT_HEIGHT + TEXT_LINE_SPACING) * (-len(text) // 2),
            w=max(len(line) for line in text) * pyxel.FONT_WIDTH + 2 * WIDGET_MARGIN,
            h=None,
            bg=COL_DEATH,
            border=None,
            text=text,
            text_col=COL_TEXT_DEATH,
        )

    def update(self) -> None:
        if pyxel.btnp(pyxel.KEY_R) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_A):
            self.game.restart()
        if pyxel.btn(pyxel.KEY_Q):
            pyxel.quit()

    @staticmethod
    def is_visible() -> bool:
        return False

    def draw(self) -> None:
        """Draw a widget with some text information."""
        self.wdg.draw()
