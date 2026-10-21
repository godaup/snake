from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pyxel

if TYPE_CHECKING:
    from snake_quest.game import Game


class GameStateHandler(ABC):
    def __init__(self, game: "Game") -> None:
        self.game: Game = game

    @staticmethod
    @abstractmethod
    def is_visible() -> bool:
        """whether the mouse is visible in this state"""
        pass

    def on_enter(self) -> None:  # noqa: B027 (optional hook)
        """Called when the game switches to this state, before its first update."""

    def get_music(self) -> int | tuple[int, ...] | None:
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
