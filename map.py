from snake import Vec2
import pyxel
from typing import TYPE_CHECKING
import omegaconf
from pathlib import Path
if TYPE_CHECKING:
    from main import Game


class Map:
    def __init__(self, level: int, game: 'Game'):
        self.cfg = omegaconf.OmegaConf.load(Path(__file__).parent / 'levels' / f'{level}.yaml')

        self.pos = Vec2(self.cfg.start.x, self.cfg.start.y)
        self.game = game

    def update(self):
        pass

    def draw(self, offset: Vec2):
        pyxel.bltm(x=0, y=self.game.cfg.header.h, tm=self.cfg.tm, u=-offset.x, v=-offset.y, w=self.game.cfg.width, h=self.game.cfg.area.h)


# TODO interpret tilemap elements (find walls)
