from snake import Vec2
import pyxel

class Map:

    def __init__(self, level: int):
        self.pos = Vec2(100, 100)

    def update(self):
        pass

    def draw(self):
        pyxel.cls(col=3)
