"""Level select: start a new game from the first level of any arc that is open (the first one, and each one after an
arc played through, see `profile.arcs_done`)."""

from typing import TYPE_CHECKING

import pyxel

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
    down,
    panel,
    up,
)

if TYPE_CHECKING:
    from snake_quest.game import Game

ITEM_SPACING = 14
PANEL_W = 200


class SelectStateHandler(GameStateHandler):
    def __init__(self, game: "Game"):
        super().__init__(game=game)
        self.title = Title("CHOOSE ARC", scale=2)
        self.height = game.cfg.header.h + game.cfg.area.h + game.cfg.footer.h
        self.selected = 0
        self.top = 70

    @staticmethod
    def is_visible() -> bool:
        return True

    def get_music(self) -> int | None:
        return MENU_MUSIC

    def on_enter(self) -> None:
        self.selected = len(self.game.unlocked_arcs()) - 1  # the furthest one

    def label(self, index: int) -> str:
        arc = self.game.campaign.arcs[index]
        if arc not in self.game.unlocked_arcs():
            return f"{index + 1}  {arc.name.upper()}   LOCKED"
        return f"{index + 1}  {arc.name.upper()}   LEVEL {arc.first}"

    def item_rect(self, index: int) -> tuple[int, int, int, int]:
        return (self.game.cfg.width - PANEL_W) // 2 + 4, self.top + index * ITEM_SPACING - 3, PANEL_W - 8, 11

    def choose(self, index: int) -> None:
        arc = self.game.campaign.arcs[index]
        if arc in self.game.unlocked_arcs():
            self.game.start_arc(arc)

    def update(self) -> None:
        self.game.backdrop.update(self.game.dt)
        count = len(self.game.campaign.arcs)
        if up():
            self.selected = (self.selected - 1) % count
        if down():
            self.selected = (self.selected + 1) % count
        for index in range(count):
            x, y, w, h = self.item_rect(index)
            if x <= pyxel.mouse_x < x + w and y <= pyxel.mouse_y < y + h:
                self.selected = index
                if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                    self.choose(index)
                    return
        if back():
            self.game.change_state(StateID.MENU)
        elif confirm():
            self.choose(self.selected)

    def draw(self) -> None:
        width = self.game.cfg.width
        self.game.backdrop.draw()
        self.title.draw(width / 2, 40, self.game.backdrop.t)
        arcs = self.game.campaign.arcs
        unlocked = self.game.unlocked_arcs()
        panel((width - PANEL_W) // 2, self.top - 10, PANEL_W, len(arcs) * ITEM_SPACING + 14)
        for index, arc in enumerate(arcs):
            y = self.top + index * ITEM_SPACING
            col = COL_HIGHLIGHT if index == self.selected else COL_TEXT if arc in unlocked else COL_DIM
            if index == self.selected:
                x, _, w, _ = self.item_rect(index)
                pyxel.text(x + 4, y, ">", COL_HIGHLIGHT)
                pyxel.text(x + w - 8, y, "<", COL_HIGHLIGHT)
            centered_text(y, self.label(index), col, width)
        centered_text(self.height - 22, "ENTER: PLAY   ESC: BACK", COL_DIM, width)
