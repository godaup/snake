from typing import Optional

from abstract import GameState
from main import Game
import pyxel
from map import Map
from snake import Snake

HEIGHT_SCORE = pyxel.FONT_HEIGHT
COL_SCORE = 6
COL_SCORE_BACKGROUND = 5


class RunningState(GameState):

    def __init__(self, game: Game):
        super().__init__(game=game)
        self.map = Map(level=game.level_counter)
        self.snake = Snake()

    @staticmethod
    def is_visible() -> bool:
        return False

    def get_music(self) -> Optional[int]:
        return 0

    def update(self) -> None:
        pass

    def draw(self) -> None:
        """Draw the score at the top."""
        score = f"{self.game.score:04}"
        pyxel.rect(0, 0, self.game.cfg.width, HEIGHT_SCORE, self.game.background)
        pyxel.text(1, 1, score, COL_SCORE)
