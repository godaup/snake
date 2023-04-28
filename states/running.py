from abstract import GameState
from main import Game

from map import Map
from snake import Snake


class RunningState(GameState):

    def __init__(self, game: Game):
        super().__init__(game=game)
        self.map = Map(level=game.level_counter)
        self.snake = Snake()

    def update(self) -> None:
        pass

    def draw(self) -> None:
        pass
