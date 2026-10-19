"""Shown when a level's goals are met: ticked-off goals and level stats. Enter goes on to the next level."""

from dataclasses import dataclass

import pyxel

from snake_quest.hud import BigText
from snake_quest.states.menu_common import COL_DIM, COL_HIGHLIGHT, COL_TEXT, centered_text, confirm, panel, text_width
from snake_quest.states.overlay import OverlayStateHandler

PANEL_W = 220
LINE_H = 9
COL_TITLE, COL_CHECK = 10, 11


@dataclass
class LevelStats:
    goals: list[str]
    seconds: float
    points: int
    length: int
    score: int
    last_level: bool


def format_time(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02}"


class LevelCompleteStateHandler(OverlayStateHandler):
    def __init__(self, game):
        super().__init__(game=game)
        self.title = BigText(scale=2)
        self.stats: LevelStats | None = None
        self.t = 0.0

    def on_enter(self) -> None:
        """Snapshot the finished level, so the numbers don't change while the screen is shown."""
        running = self.running
        self.t = 0.0
        self.stats = LevelStats(
            goals=[goal.status(running.map, running.snake) for goal in running.map.goals],
            seconds=running.elapsed,
            points=self.game.score - running.score_at_start,
            length=len(running.snake),
            score=self.game.score,
            last_level=self.game.level_counter == len(self.game.campaign),
        )
        self.game.sm.effect("win")

    def update(self) -> None:
        self.t += self.game.dt.total_seconds()
        # a short grace period, so a key still held from playing does not skip the screen
        if self.t > 0.4 and (confirm() or pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)):
            self.game.level_up()

    def stat_rows(self) -> list[tuple[str, str]]:
        stats = self.stats
        return [
            ("TIME", format_time(stats.seconds)),
            ("POINTS", f"+{stats.points}"),
            ("LENGTH", str(stats.length)),
            ("SCORE", f"{stats.score:05}"),
        ]

    def draw_overlay(self) -> None:
        if self.stats is None:
            return
        width = self.game.cfg.width
        rows = len(self.stats.goals) + len(self.stat_rows())
        height = 58 + rows * LINE_H
        top = int(self.area_center_y - height / 2)
        left = (width - PANEL_W) // 2
        panel(left, top, PANEL_W, height)
        self.title.draw(width / 2, top + 12, "LEVEL COMPLETE!", COL_TITLE)
        y = top + 26
        for goal in self.stats.goals:
            line = f"   {goal}"
            x = (width - text_width(line)) // 2
            self.draw_check(x, y)
            pyxel.text(x, y, line, COL_TEXT)
            y += LINE_H
        y += 4
        label_x, value_right = left + 50, left + PANEL_W - 50
        for label, value in self.stat_rows():
            pyxel.text(label_x, y, label, COL_DIM)
            pyxel.text(value_right - text_width(value), y, value, COL_HIGHLIGHT if label == "SCORE" else COL_TEXT)
            y += LINE_H
        prompt = "ENTER: FINISH" if self.stats.last_level else "ENTER: NEXT LEVEL"
        if int(self.t * 2) % 2 == 0:
            centered_text(top + height - 10, prompt, COL_DIM, width)

    @staticmethod
    def draw_check(x: int, y: int) -> None:
        """A small tick mark in front of a goal line (the built-in font has no check mark)."""
        pyxel.line(x, y + 3, x + 2, y + 5, COL_CHECK)
        pyxel.line(x + 2, y + 5, x + 6, y, COL_CHECK)
