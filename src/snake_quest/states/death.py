import pyxel

from snake_quest.states import StateID
from snake_quest.states.abstract import GameStateHandler
from snake_quest.widget import TEXT_LINE_SPACING, WIDGET_MARGIN, Widget

COL_TEXT_DEATH = 0
COL_DEATH = 8


class DeathStateHandler(GameStateHandler):
    TITLE = "GAME OVER"
    BG = COL_DEATH

    def __init__(self, game):
        super().__init__(game=game)
        self.rank: int | None = None
        self.wdg = self.build_widget([self.TITLE, "(R)ESTART", "(M)ENU", "(Q)UIT"])

    def on_enter(self) -> None:
        """Record the score and show it, with the highscore rank if it made the table."""
        played = self.game.difficulty
        self.rank = self.game.profile.add_highscore(self.game.score, self.game.level_counter, played.name)
        self.game.sm.effect("death")
        lines = [self.TITLE, f"SCORE {self.game.score}"]
        if self.rank:
            lines.append(f"NEW {played.label} HIGHSCORE #{self.rank}!")
        self.wdg = self.build_widget([*lines, "", "(R)ESTART", "(M)ENU", "(Q)UIT"])

    def build_widget(self, text: list[str]) -> Widget:
        return Widget(
            x=min([self.center_text(line) for line in text]) - WIDGET_MARGIN,
            y=self.game.cfg.area.h // 2
            + self.game.cfg.header.h
            + (pyxel.FONT_HEIGHT + TEXT_LINE_SPACING) * (-len(text) // 2),
            w=max(len(line) for line in text) * pyxel.FONT_WIDTH + 2 * WIDGET_MARGIN,
            h=None,
            bg=self.BG,
            border=None,
            text=text,
            text_col=COL_TEXT_DEATH,
        )

    def update(self) -> None:
        if pyxel.btnp(pyxel.KEY_R) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_A):
            self.game.restart()
        if pyxel.btnp(pyxel.KEY_M) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_B):
            self.game.change_state(StateID.MENU)
        if pyxel.btn(pyxel.KEY_Q):
            pyxel.quit()

    @staticmethod
    def is_visible() -> bool:
        return False

    def draw(self) -> None:
        """Draw a widget with some text information."""
        self.wdg.draw()
