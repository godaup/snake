from abstract import GameState
import pyxel


class MenuState(GameState):
    @staticmethod
    def is_visible() -> bool:
        return True

    def update(self) -> None:
        pass

    def draw(self) -> None:
        pyxel.cls(col=self.game.background)
