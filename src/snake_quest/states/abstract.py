"""The base of every state handler: what the game loop calls in each `StateID`."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pyxel

if TYPE_CHECKING:
    from snake_quest.game import Game


class GameStateHandler(ABC):
    """One screen of the game (menu, a running level, pause, ...). `Game` keeps one per `StateID` and calls the current
    one's `update` and `draw` every frame."""

    def __init__(self, game: "Game") -> None:
        self.game: Game = game

    @staticmethod
    @abstractmethod
    def is_visible() -> bool:
        """Whether the mouse cursor is shown in this state."""

    def on_enter(self) -> None:  # noqa: B027 (optional hook)
        """Called when the game switches to this state, before its first update."""

    def get_music(self) -> int | tuple[int, ...] | None:
        """The music to play in this state: a music number, a tuple of sounds looped per channel, or None."""
        return None

    @abstractmethod
    def update(self) -> None:
        """Called every frame: read input, advance the state, ask the game for another state."""

    @abstractmethod
    def draw(self) -> None:
        """Called every frame after `update`: draw the screen."""

    def center_text(self, text, char_width=pyxel.FONT_WIDTH) -> int:
        """Helper function for calculating the start x value for centered text."""

        text_width = len(text) * char_width
        return (self.game.cfg.width - text_width) // 2
