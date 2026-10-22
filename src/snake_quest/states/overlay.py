"""Base for screens shown on top of a paused level (mission, countdown, level complete)."""

from abc import abstractmethod

import pyxel

from snake_quest.states.abstract import GameStateHandler

DIM_ALPHA = 0.5


class OverlayStateHandler(GameStateHandler):
    """Every frame redraws the frozen level (map, snake, HUD) and dims the play area, then draws the overlay on top.
    Redrawing keeps animated overlays clean: drawing onto the previous frame would leave smears."""

    @staticmethod
    def is_visible() -> bool:
        return True

    @property
    def running(self):
        """The running level drawn underneath."""
        return self.game.running_handler

    def get_music(self) -> int | tuple[int, ...] | None:
        """The level's music plays on (so it doesn't start over after the briefing or a pause)."""
        return self.running.get_music()

    def draw(self) -> None:
        self.running.draw()
        self.dim()
        self.draw_overlay()

    def dim(self) -> None:
        """Darken the play area with a dither, so the panel stands out from the level."""
        pyxel.dither(DIM_ALPHA)
        pyxel.rect(0, self.game.cfg.header.h, self.game.cfg.width, self.game.cfg.area.h, 0)
        pyxel.dither(1.0)

    @property
    def area_center_y(self) -> float:
        """The vertical middle of the play area in screen px."""
        return self.game.cfg.header.h + self.game.cfg.area.h / 2

    @abstractmethod
    def draw_overlay(self) -> None:
        """Draw the state's own panel over the dimmed level."""
