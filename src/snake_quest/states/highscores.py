from snake_quest import difficulty
from snake_quest.profile import MAX_HIGHSCORES
from snake_quest.states import StateID
from snake_quest.states.abstract import GameStateHandler
from snake_quest.states.menu_common import (
    COL_DIM,
    COL_HIGHLIGHT,
    COL_TEXT,
    MENU_MUSIC,
    Title,
    back,
    centered_text,
    confirm,
    left,
    panel,
    right,
)

ROW_H = 10
PANEL_W = 200


class HighscoresStateHandler(GameStateHandler):
    def __init__(self, game):
        super().__init__(game=game)
        self.title = Title("HIGHSCORES", scale=2)
        self.height = game.cfg.header.h + game.cfg.area.h + game.cfg.footer.h
        self.shown = difficulty.DEFAULT  # whose table is on screen; one table per difficulty

    @staticmethod
    def is_visible() -> bool:
        return True

    def get_music(self) -> int | None:
        return MENU_MUSIC

    def on_enter(self) -> None:
        self.shown = self.game.difficulty.name  # start with the table of the difficulty played

    def update(self) -> None:
        self.game.backdrop.update(self.game.dt)
        if left():
            self.shown = difficulty.next_name(self.shown, -1)
        if right():
            self.shown = difficulty.next_name(self.shown)
        if back() or confirm():
            self.game.change_state(StateID.MENU)

    def rows(self) -> list[str]:
        scores = self.game.profile.table(self.shown)
        if not scores:
            return []
        return [f"{rank:>2}.  {h.score:>6}   LEVEL {h.level:<2}   {h.date}" for rank, h in enumerate(scores, start=1)]

    def draw(self) -> None:
        width = self.game.cfg.width
        self.game.backdrop.draw()
        self.title.draw(width / 2, 30, self.game.backdrop.t)
        top = 50
        panel((width - PANEL_W) // 2, top, PANEL_W, MAX_HIGHSCORES * ROW_H + 26)
        centered_text(top - 9, f"<  {self.shown.upper()}  >", COL_HIGHLIGHT, width)
        rows = self.rows()
        if not rows:
            centered_text(top + 50, "NO SCORES YET - GO PLAY!", COL_DIM, width)
        for index, row in enumerate(rows):
            centered_text(top + 10 + index * ROW_H, row, COL_HIGHLIGHT if index == 0 else COL_TEXT, width)
        centered_text(self.height - 22, "LEFT / RIGHT: DIFFICULTY   ESC / ENTER: BACK", COL_DIM, width)
