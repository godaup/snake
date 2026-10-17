from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pyxel

from widget import Widget

if TYPE_CHECKING:
    from main import Game


class GameStateHandler(ABC):
    def __init__(self, game: "Game") -> None:
        self.game: Game = game
        self.header = Widget(
            x=0,
            y=0,
            h=self.game.cfg.header.h,
            w=self.game.cfg.width,
            bg=self.game.cfg.header.bg,
            border=self.game.cfg.header.border,
        )
        self.footer = Widget(
            x=0,
            y=self.game.cfg.header.h + self.game.cfg.area.h,
            h=self.game.cfg.footer.h,
            w=self.game.cfg.width,
            bg=self.game.cfg.footer.bg,
            border=self.game.cfg.footer.border,
        )

    @staticmethod
    @abstractmethod
    def is_visible() -> bool:
        """whether the mouse is visible in this state"""
        pass

    def get_music(self) -> int | None:
        """if music should be played return id"""
        return None

    @abstractmethod
    def update(self) -> None:
        pass

    @abstractmethod
    def draw(self) -> None:
        pass

    def center_text(self, text, char_width=pyxel.FONT_WIDTH) -> int:
        """Helper function for calculating the start x value for centered text."""

        text_width = len(text) * char_width
        return (self.game.cfg.width - text_width) // 2
