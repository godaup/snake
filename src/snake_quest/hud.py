"""Header and footer while a level is running.

Header: level number and title (left), the score in big digits (centre), best score and snake length (right).
Footer: one entry per level goal, its status text plus a progress bar when the goal is measurable.
"""

from typing import TYPE_CHECKING

import pyxel

from snake_quest.entity import Apple

if TYPE_CHECKING:
    from snake_quest.game import Game
    from snake_quest.map import Map
    from snake_quest.snake import Snake

COL_BORDER, COL_LABEL, COL_VALUE, COL_ACCENT = 5, 13, 7, 10
COL_BAR_BG, COL_BAR, COL_BAR_DONE = 5, 11, 10
SCORE_SCALE = 2
BAR_H = 4
MARGIN = 4


class BigText:
    """Text drawn scaled; the image is only re-rendered when the text changes."""

    def __init__(self, scale: int):
        self.scale = scale
        self.text = None
        self.image = None

    def draw(self, center_x: float, center_y: float, text: str, col: int) -> None:
        if text != self.text:
            self.text = text
            self.image = pyxel.Image(len(text) * pyxel.FONT_WIDTH, pyxel.FONT_HEIGHT)
            self.image.cls(0)
            self.image.text(0, 0, text, 7)
        w, h = self.image.width, self.image.height
        pyxel.pal(7, col)
        pyxel.blt(center_x - w / 2, center_y - h / 2, self.image, 0, 0, w, h, colkey=0, scale=self.scale)
        pyxel.pal()

    @property
    def width(self) -> int:
        return 0 if self.image is None else self.image.width * self.scale


class Hud:
    def __init__(self, game: "Game", level_map: "Map", snake: "Snake"):
        self.game = game
        self.map = level_map
        self.snake = snake
        self.score_text = BigText(SCORE_SCALE)
        self.width = game.cfg.width
        self.header_h = game.cfg.header.h
        self.footer_y = game.cfg.header.h + game.cfg.area.h
        self.footer_h = game.cfg.footer.h

    def draw(self) -> None:
        self.draw_header()
        self.draw_footer()

    # ---- header -------------------------------------------------------------------------------------------------

    def level_lines(self) -> tuple[str, str]:
        return f"LEVEL {self.game.level_counter}", str(self.map.cfg.get("title", self.map.level.name))

    def right_lines(self) -> tuple[str, str]:
        scores = self.game.profile.highscores
        best = max(scores[0].score if scores else 0, self.game.score)
        return f"BEST {best}", f"LENGTH {len(self.snake)}"

    def draw_header(self) -> None:
        pyxel.rect(0, 0, self.width, self.header_h, self.game.cfg.header.bg)
        pyxel.line(0, self.header_h - 1, self.width - 1, self.header_h - 1, COL_BORDER)
        top, bottom = 3, self.header_h - pyxel.FONT_HEIGHT - 3
        level, title = self.level_lines()
        pyxel.text(MARGIN, top, level, COL_ACCENT)
        pyxel.text(MARGIN, bottom, title, COL_VALUE)
        best, length = self.right_lines()
        for y, text in ((top, best), (bottom, length)):
            pyxel.text(self.width - MARGIN - len(text) * pyxel.FONT_WIDTH, y, text, COL_LABEL)
        # score in the middle, with an apple in front
        center_x, center_y = self.width / 2 + 6, (self.header_h - 1) / 2
        self.score_text.draw(center_x, center_y, f"{self.game.score:05}", COL_VALUE)
        apple_x = center_x - self.score_text.width / 2 - 12
        pyxel.blt(apple_x, center_y - 4, 0, Apple._img_x * 8, Apple._img_y * 8, 8, 8, colkey=0)

    # ---- footer -------------------------------------------------------------------------------------------------

    def goal_entries(self) -> list[tuple[str, float | None]]:
        return [(goal.status(self.map, self.snake), goal.progress(self.map, self.snake)) for goal in self.map.goals]

    def draw_footer(self) -> None:
        y = self.footer_y
        pyxel.rect(0, y, self.width, self.footer_h, self.game.cfg.footer.bg)
        pyxel.line(0, y, self.width - 1, y, COL_BORDER)
        entries = self.goal_entries()
        slot_w = self.width // max(len(entries), 1)
        text_y = y + (self.footer_h - pyxel.FONT_HEIGHT) // 2 + 1
        for index, (status, progress) in enumerate(entries):
            x = index * slot_w + MARGIN
            done = progress is not None and progress >= 1
            pyxel.text(x, text_y, status, COL_ACCENT if done else COL_VALUE)
            if progress is None:
                continue
            bar_x = x + len(status) * pyxel.FONT_WIDTH + MARGIN
            bar_w = (index + 1) * slot_w - MARGIN - bar_x
            if bar_w < 8:
                continue
            bar_y = y + (self.footer_h - BAR_H) // 2 + 1
            pyxel.rect(bar_x, bar_y, bar_w, BAR_H, COL_BAR_BG)
            pyxel.rect(bar_x, bar_y, round(bar_w * progress), BAR_H, COL_BAR_DONE if done else COL_BAR)
