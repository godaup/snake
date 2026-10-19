"""Mission briefing shown when a level starts: level, title, intro text and goals. Enter starts the countdown."""

import pyxel

from snake_quest.hud import BigText
from snake_quest.states import StateID
from snake_quest.states.menu_common import (
    COL_DIM,
    COL_HIGHLIGHT,
    COL_TEXT,
    back,
    centered_text,
    confirm,
    panel,
)
from snake_quest.states.overlay import OverlayStateHandler

PANEL_W = 220
LINE_H = 9
COL_TITLE = 11


class MissionStateHandler(OverlayStateHandler):
    def __init__(self, game):
        super().__init__(game=game)
        self.title = BigText(scale=2)
        self.t = 0.0

    def on_enter(self) -> None:
        self.t = 0.0

    def lines(self) -> dict:
        level_map = self.running.map
        level = level_map.level
        return {
            "kicker": f"LEVEL {level.number} OF {len(self.game.campaign)}  -  {level.arc.upper()}"
            f"  -  {self.game.difficulty.label}",
            "title": str(level_map.cfg.get("title", level.name)).upper(),
            "intro": [str(line) for line in level_map.cfg.get("intro", [])],
            "goals": [goal.describe() for goal in level_map.goals],
        }

    def update(self) -> None:
        self.t += self.game.dt.total_seconds()
        if confirm() or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            self.game.change_state(StateID.COUNTDOWN)
        elif back():
            self.game.change_state(StateID.MENU)

    def draw_overlay(self) -> None:
        width = self.game.cfg.width
        content = self.lines()
        rows = len(content["intro"]) + len(content["goals"])
        height = 64 + rows * LINE_H
        top = int(self.area_center_y - height / 2)
        panel((width - PANEL_W) // 2, top, PANEL_W, height)
        centered_text(top + 6, content["kicker"], COL_DIM, width)
        self.title.draw(width / 2, top + 22, content["title"], COL_TITLE)
        y = top + 34
        for line in content["intro"]:
            centered_text(y, line, COL_TEXT, width)
            y += LINE_H
        y += 3
        centered_text(y, "MISSION", COL_HIGHLIGHT, width)
        y += LINE_H + 1
        for goal in content["goals"]:
            centered_text(y, f"> {goal}", COL_TEXT, width)
            y += LINE_H
        if int(self.t * 2) % 2 == 0:  # blinking prompt
            centered_text(top + height - 10, "ENTER: START    ESC: MENU", COL_DIM, width)
