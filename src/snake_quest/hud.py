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
COL_BOOST = 12  # same blue as the speed apple
COL_BOSS, COL_BOSS_BG, COL_BOSS_PANEL = 8, 2, 0
BOSS_BAR_W = 120
BANNER_SECONDS = 2.5  # how long a boss's phase message is shown
SCORE_SCALE = 2
BAR_H = 4
MARGIN = 4


class BigText:
    """Text drawn scaled; the image is only re-rendered when the text changes."""

    def __init__(self, scale: int):
        self.scale = scale
        self.text = None
        self.image = None

    def draw(self, center_x: float, center_y: float, text: str, col: int, scale: float | None = None) -> None:
        """Draw centred at (center_x, center_y); `scale` overrides the default, e.g. for a pulsing countdown."""
        if text != self.text:
            self.text = text
            self.image = pyxel.Image(len(text) * pyxel.FONT_WIDTH, pyxel.FONT_HEIGHT)
            self.image.cls(0)
            self.image.text(0, 0, text, 7)
        w, h = self.image.width, self.image.height
        pyxel.pal(7, col)
        scale = self.scale if scale is None else scale
        pyxel.blt(center_x - w / 2, center_y - h / 2, self.image, 0, 0, w, h, colkey=0, scale=scale)
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
        self.banner_text = BigText(SCORE_SCALE)
        self.width = game.cfg.width
        self.header_h = game.cfg.header.h
        self.footer_y = game.cfg.header.h + game.cfg.area.h
        self.footer_h = game.cfg.footer.h

    def draw(self) -> None:
        self.draw_header()
        self.draw_footer()
        if self.map.boss:
            self.draw_boss()

    # ---- header -------------------------------------------------------------------------------------------------

    def level_lines(self) -> tuple[str, str]:
        return f"LEVEL {self.game.level_counter}", str(self.map.cfg.get("title", self.map.level.name))

    def right_lines(self) -> tuple[str, str]:
        """Best score and length; an active speed boost takes the place of the best score."""
        length = f"LENGTH {len(self.snake)}"
        if self.snake.weapon is not None:
            length = f"{self.snake.weapon.name} {self.snake.weapon.ammo}  {length}"
        if self.snake.boost_left > 0:
            percent = round((self.snake.boost_factor - 1) * 100)
            return f"SPEED {percent:+}% {self.snake.boost_left:.1f}s", length
        arc = self.game.campaign.arc_of(self.game.level_counter).name
        scores = self.game.profile.table(self.game.difficulty.name, arc)
        best = max(scores[0].score if scores else 0, self.game.score)
        return f"BEST {best}", length

    def draw_header(self) -> None:
        pyxel.rect(0, 0, self.width, self.header_h, self.game.cfg.header.bg)
        pyxel.line(0, self.header_h - 1, self.width - 1, self.header_h - 1, COL_BORDER)
        top, bottom = 3, self.header_h - pyxel.FONT_HEIGHT - 3
        level, title = self.level_lines()
        pyxel.text(MARGIN, top, level, COL_ACCENT)
        pyxel.text(MARGIN, bottom, title, COL_VALUE)
        best, length = self.right_lines()
        for y, text in ((top, best), (bottom, length)):
            col = COL_BOOST if text.startswith("SPEED") else COL_LABEL
            pyxel.text(self.width - MARGIN - len(text) * pyxel.FONT_WIDTH, y, text, col)
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

    # ---- boss ---------------------------------------------------------------------------------------------------

    def draw_boss(self) -> None:
        """The boss bar at the top of the play area, and its phase message for a moment when a phase starts."""
        boss = self.map.boss
        label = boss.label()
        label_w = len(label) * pyxel.FONT_WIDTH
        total_w = label_w + MARGIN + BOSS_BAR_W
        x, y = (self.width - total_w) // 2, self.header_h + 2
        pyxel.rect(x - 2, y - 1, total_w + 4, pyxel.FONT_HEIGHT + 2, COL_BOSS_PANEL)
        pyxel.text(x, y, label, COL_BOSS)
        bar_x, bar_y = x + label_w + MARGIN, y + (pyxel.FONT_HEIGHT - BAR_H) // 2
        fill = min(max(boss.bar(self.map, self.snake), 0.0), 1.0)
        pyxel.rect(bar_x, bar_y, BOSS_BAR_W, BAR_H, COL_BOSS_BG)
        pyxel.rect(bar_x, bar_y, round(BOSS_BAR_W * fill), BAR_H, COL_BOSS)
        message = boss.phase_message()
        if message and boss.phase > 0 and boss.since_phase < BANNER_SECONDS and pyxel.frame_count % 16 < 12:
            center_y = self.header_h + (self.footer_y - self.header_h) * 0.3
            self.banner_text.draw(self.width / 2, center_y, message, COL_BOSS)
