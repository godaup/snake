from abstract import GameState


class PauseState(GameState):

    @staticmethod
    def is_visible() -> bool:
        return False

    def update(self) -> None:
        pass

    def draw(self) -> None:
        pass
