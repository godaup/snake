from abc import ABC, abstractmethod

from main import Game
from typing import Optional


class GameState(ABC):
    def __init__(self, game: Game) -> None:
        self.game: Game = game

    @staticmethod
    @abstractmethod
    def is_visible() -> bool:
        pass

    def get_music(self) -> Optional[int]:
        return None

    @abstractmethod
    def update(self) -> None:
        pass

    @abstractmethod
    def draw(self) -> None:
        pass
