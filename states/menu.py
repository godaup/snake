from .abstract import GameStateHandler
import pyxel


class MenuStateHandler(GameStateHandler):
    @staticmethod
    def is_visible() -> bool:
        return True

    def update(self) -> None:
        pass

    def draw(self) -> None:
        pyxel.cls(col=self.game.background)
