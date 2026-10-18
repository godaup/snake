from snake_quest.states import StateID
from snake_quest.states.abstract import GameStateHandler
from snake_quest.states.menu_common import COL_DIM, COL_HIGHLIGHT, COL_TEXT, MENU_MUSIC, back, centered_text, confirm

# (text, highlighted); an empty line is a gap
CREDITS = [
    ("SNAKE QUEST", True),
    ("", False),
    ("GAME DESIGN & CODE", True),
    ("Patrick Godau", False),
    ("", False),
    ("ENGINE", True),
    ("Pyxel by Takashi Kitao", False),
    ("(MIT License)", False),
    ("", False),
    ("CONFIGURATION", True),
    ("OmegaConf", False),
    ("", False),
    ("THANKS FOR PLAYING!", True),
]
LINE_H = 10
SCROLL_SPEED = 14  # px per second


class CreditsStateHandler(GameStateHandler):
    def __init__(self, game):
        super().__init__(game=game)
        self.height = game.cfg.header.h + game.cfg.area.h + game.cfg.footer.h
        self.offset = 0.0

    @staticmethod
    def is_visible() -> bool:
        return True

    def get_music(self) -> int | None:
        return MENU_MUSIC

    def on_enter(self) -> None:
        self.offset = 0.0  # start from the bottom every time

    def update(self) -> None:
        self.game.backdrop.update(self.game.dt)
        self.offset += SCROLL_SPEED * min(self.game.dt.total_seconds(), 0.1)
        # loop once the last line has scrolled out at the top
        if self.offset > self.height + len(CREDITS) * LINE_H:
            self.offset = 0.0
        if back() or confirm():
            self.game.change_state(StateID.MENU)

    def draw(self) -> None:
        width = self.game.cfg.width
        self.game.backdrop.draw()
        for index, (text, highlighted) in enumerate(CREDITS):
            y = self.height - self.offset + index * LINE_H
            if 12 <= y <= self.height - 30:  # keep clear of the hedge frame and the hint line
                centered_text(int(y), text, COL_HIGHLIGHT if highlighted else COL_TEXT, width)
        centered_text(self.height - 22, "ESC / ENTER: BACK", COL_DIM, width)
