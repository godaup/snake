"""Pause overlay: Resume or back to the menu.

Built on OverlayStateHandler, which redraws the level every frame. The pause screen shows the mouse cursor, and Pyxel
draws the cursor into the screen image: without a full redraw every cursor position stayed behind as a trail."""

from collections.abc import Callable

import pyxel

from snake_quest.hud import BigText
from snake_quest.states import StateID
from snake_quest.states.menu_common import COL_DIM, COL_HIGHLIGHT, COL_TEXT, centered_text, confirm, down, panel, up
from snake_quest.states.overlay import OverlayStateHandler

PANEL_W, PANEL_H = 140, 64
ITEM_SPACING = 12


class PauseStateHandler(OverlayStateHandler):
    def __init__(self, game):
        super().__init__(game=game)
        self.title = BigText(scale=2)
        self.items: list[tuple[str, Callable[[], None]]] = [
            ("RESUME", lambda: self.game.change_state(StateID.RUNNING)),
            ("MENU", lambda: self.game.change_state(StateID.MENU)),
        ]
        self.selected = 0

    def on_enter(self) -> None:
        self.selected = 0

    @property
    def top(self) -> int:
        return int(self.area_center_y - PANEL_H / 2)

    def item_rect(self, index: int) -> tuple[int, int, int, int]:
        width = self.game.cfg.width
        return (width - PANEL_W) // 2 + 4, self.top + 30 + index * ITEM_SPACING - 2, PANEL_W - 8, 10

    def update(self) -> None:
        if pyxel.btnp(pyxel.KEY_P) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_START):
            self.game.change_state(StateID.RUNNING)
            return
        if pyxel.btnp(pyxel.KEY_ESCAPE) or pyxel.btnp(pyxel.GAMEPAD1_BUTTON_B):
            self.game.change_state(StateID.MENU)
            return
        if up():
            self.selected = (self.selected - 1) % len(self.items)
        if down():
            self.selected = (self.selected + 1) % len(self.items)
        for index in range(len(self.items)):
            x, y, w, h = self.item_rect(index)
            if x <= pyxel.mouse_x < x + w and y <= pyxel.mouse_y < y + h:
                self.selected = index
                if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                    self.items[index][1]()
                    return
        if confirm():
            self.items[self.selected][1]()

    def draw_overlay(self) -> None:
        width = self.game.cfg.width
        panel((width - PANEL_W) // 2, self.top, PANEL_W, PANEL_H)
        self.title.draw(width / 2, self.top + 13, "PAUSED", COL_HIGHLIGHT)
        for index, (label, _) in enumerate(self.items):
            x, y, w, _ = self.item_rect(index)
            selected = index == self.selected
            if selected:
                pyxel.text(x + 4, y + 2, ">", COL_HIGHLIGHT)
                pyxel.text(x + w - 8, y + 2, "<", COL_HIGHLIGHT)
            centered_text(y + 2, label, COL_HIGHLIGHT if selected else COL_TEXT, width)
        centered_text(self.top + PANEL_H - 9, "P: RESUME   ESC: MENU", COL_DIM, width)
