from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING
import pyxel

if TYPE_CHECKING:
    from main import Game


class GameStateHandler(ABC):
    def __init__(self, game: 'Game') -> None:
        self.game: 'Game' = game

    @staticmethod
    @abstractmethod
    def is_visible() -> bool:
        """whether the mouse is visible in this state"""
        pass

    def get_music(self) -> Optional[int]:
        """if music should be played return id"""
        return None

    @abstractmethod
    def update(self) -> None:
        pass

    @abstractmethod
    def draw(self) -> None:
        pass

    def center_text(self, text, char_width=pyxel.FONT_WIDTH):
        """Helper function for calculating the start x value for centered text."""

        text_width = len(text) * char_width
        return (self.game.cfg.width - text_width) // 2
