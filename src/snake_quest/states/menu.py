"""The main menu."""

from collections.abc import Callable
from typing import TYPE_CHECKING

import pyxel

from snake_quest import __version__, difficulty
from snake_quest.states import StateID
from snake_quest.states.abstract import GameStateHandler
from snake_quest.states.menu_common import (
    COL_DIM,
    COL_HIGHLIGHT,
    COL_TEXT,
    MENU_MUSIC,
    Title,
    centered_text,
    confirm,
    down,
    left,
    panel,
    right,
    text_width,
    up,
)

if TYPE_CHECKING:
    from snake_quest.game import Game

ITEM_SPACING = 12
PANEL_W = 128
DIFFICULTY_ITEM = 1


class MenuStateHandler(GameStateHandler):
    """The main menu over the backdrop: play, difficulty, highscores, customize, settings, credits and quit, with the
    keys or the mouse."""

    def __init__(self, game: "Game"):
        super().__init__(game=game)
        self.title = Title("SNAKE QUEST")
        self.items: list[tuple[str, Callable[[], None]]] = [
            ("PLAY", self.game.play),
            ("DIFFICULTY", lambda: self.change_difficulty(1)),
            ("HIGHSCORES", lambda: self.game.change_state(StateID.HIGHSCORES)),
            ("CUSTOMIZE", lambda: self.game.change_state(StateID.CUSTOMIZE)),
            ("SETTINGS", lambda: self.game.change_state(StateID.SETTINGS)),
            ("CREDITS", lambda: self.game.change_state(StateID.CREDITS)),
            ("QUIT", pyxel.quit),
        ]
        self.selected = 0
        self.height = game.cfg.header.h + game.cfg.area.h + game.cfg.footer.h
        self.items_top = self.height // 2 - 6

    @staticmethod
    def is_visible() -> bool:
        return True

    def get_music(self) -> int | None:
        return MENU_MUSIC

    def change_difficulty(self, step: int) -> None:
        """Choose the next (or previous) difficulty for new games; saved with the profile."""
        profile = self.game.profile
        profile.difficulty = difficulty.next_name(profile.difficulty, step)
        profile.save()

    def label(self, index: int) -> str:
        """Item `index`'s text; the difficulty item shows the difficulty chosen."""
        label = self.items[index][0]
        if index == DIFFICULTY_ITEM:
            return f"{label}  {self.game.profile.difficulty.upper()}"
        return label

    def item_rect(self, index: int) -> tuple[int, int, int, int]:
        """(x, y, w, h) of item `index`, for drawing it and for the mouse."""
        return (self.game.cfg.width - PANEL_W) // 2 + 4, self.items_top + index * ITEM_SPACING - 2, PANEL_W - 8, 10

    def update(self) -> None:
        self.game.backdrop.update(self.game.dt)
        if up():
            self.selected = (self.selected - 1) % len(self.items)
        if down():
            self.selected = (self.selected + 1) % len(self.items)
        # mouse: hovering selects, clicking activates
        for index in range(len(self.items)):
            x, y, w, h = self.item_rect(index)
            if x <= pyxel.mouse_x < x + w and y <= pyxel.mouse_y < y + h:
                self.selected = index
                if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                    self.items[index][1]()
                    return
        if self.selected == DIFFICULTY_ITEM and (left() or right()):
            self.change_difficulty(-1 if left() else 1)
        if pyxel.btnp(pyxel.KEY_P):  # the old shortcut keeps working
            self.game.play()
        elif confirm():
            self.items[self.selected][1]()

    def draw(self) -> None:
        width = self.game.cfg.width
        self.game.backdrop.draw()
        self.title.draw(width / 2, 48, self.game.backdrop.t)
        panel_h = len(self.items) * ITEM_SPACING + 8
        panel((width - PANEL_W) // 2, self.items_top - 6, PANEL_W, panel_h)
        for index in range(len(self.items)):
            label = self.label(index)
            y = self.items_top + index * ITEM_SPACING
            if index == self.selected:
                x, _, w, _ = self.item_rect(index)
                pyxel.text(x + 4, y, ">", COL_HIGHLIGHT)
                pyxel.text(x + w - 8, y, "<", COL_HIGHLIGHT)
            centered_text(y, label, COL_HIGHLIGHT if index == self.selected else COL_TEXT, width)
        hint = "ARROWS + ENTER  /  MOUSE"
        centered_text(self.height - 22, hint, COL_DIM, width)
        version = f"v{__version__}"
        pyxel.text(width - text_width(version) - 12, self.height - 22, version, COL_DIM)
