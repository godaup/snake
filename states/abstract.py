from abc import ABC, abstractmethod

from main import Game


class GameState(ABC):
    def __init__(self, game: Game) -> None:
        self.game = game

    @abstractmethod
    def update(self) -> None:
        pass

    @abstractmethod
    def draw(self) -> None:
        pass
