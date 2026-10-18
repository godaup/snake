import pyxel

from snake_quest.palettes import PALETTES
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

PANEL_W = 160
SWATCH = 8


class CustomizeStateHandler(GameStateHandler):
    """Pick the snake's colour palette. The backdrop snake shows the choice live; leaving saves it."""

    def __init__(self, game):
        super().__init__(game=game)
        self.title = Title("CUSTOMIZE", scale=2)
        self.height = game.cfg.header.h + game.cfg.area.h + game.cfg.footer.h
        self.names = list(PALETTES)

    @staticmethod
    def is_visible() -> bool:
        return True

    def get_music(self) -> int | None:
        return MENU_MUSIC

    @property
    def index(self) -> int:
        return self.names.index(self.game.profile.palette)

    def choose(self, index: int) -> None:
        self.game.profile.palette = self.names[index % len(self.names)]
        self.game.backdrop.recolor()

    def update(self) -> None:
        self.game.backdrop.update(self.game.dt)
        if left():
            self.choose(self.index - 1)
        if right():
            self.choose(self.index + 1)
        if back() or confirm():
            self.game.profile.save()
            self.game.change_state(StateID.MENU)

    def draw(self) -> None:
        width = self.game.cfg.width
        self.game.backdrop.draw()
        self.title.draw(width / 2, 30, self.game.backdrop.t)
        top = 60
        panel((width - PANEL_W) // 2, top, PANEL_W, 56)
        centered_text(top + 8, "SNAKE COLORS", COL_DIM, width)
        name = self.game.profile.palette.upper()
        centered_text(top + 20, f"<  {name}  >", COL_HIGHLIGHT, width)
        colors = PALETTES[self.game.profile.palette]
        swatches = [colors.head, *colors.body]
        x0 = (width - len(swatches) * (SWATCH + 2)) // 2
        for i, col in enumerate(swatches):
            pyxel.rect(x0 + i * (SWATCH + 2), top + 34, SWATCH, SWATCH, col)
        centered_text(top + 46, f"{self.index + 1} / {len(self.names)}", COL_TEXT, width)
        centered_text(self.height - 22, "LEFT / RIGHT: CHOOSE   ESC / ENTER: SAVE", COL_DIM, width)
