"""Render a whole level to a PNG for reviewing level design (`snake-quest --level NAME --preview FILE`)."""

import datetime
from pathlib import Path

import omegaconf
import pyxel

from snake_quest import difficulty
from snake_quest.campaign import Level
from snake_quest.game import SETTINGS
from snake_quest.map import Map

COL_START = 7
# path tiles are drawn as bold markers: the in-game breadcrumb (a 2x2 dot) is invisible at whole-level scale
COL_PATH, COL_PATH_RING = 10, 9


class _PreviewGame:
    """Just enough of Game for Map to load a level."""

    def __init__(self):
        self.cfg = omegaconf.OmegaConf.load(SETTINGS)
        self.score = 0
        self.dt = datetime.timedelta(0)
        self.difficulty = difficulty.load(self.cfg, difficulty.DEFAULT)


def render(level: Level, filename: Path, scale: int = 2) -> None:
    """Draw tilemap (with hedge variants), entities, the hidden path and the start position. Pyxel must be
    initialized and the campaign's sprites loaded. `filename` must be absolute: pyxel.init() changes the working
    directory."""
    game = _PreviewGame()
    level_map = Map(level=level, game=game)
    header = game.cfg.header.h
    img = pyxel.Image(level_map.cfg.width, level_map.cfg.height)
    img.cls(game.cfg.area.bg)
    img.bltm(0, 0, level_map.cfg.tm, 0, 0, level_map.cfg.width, level_map.cfg.height)
    for pos in level_map.path:
        img.circ(pos.x + 4, pos.y - header + 4, 2, COL_PATH)
        img.circb(pos.x + 4, pos.y - header + 4, 4, COL_PATH_RING)
    for ent in level_map.entities:
        img.blt(ent.pos.x, ent.pos.y - header, ent.img_b, ent.img_x, ent.img_y, ent.w, ent.h, colkey=0)
    start_x, start_y = level_map.start.x, level_map.start.y - header
    img.circ(start_x, start_y, 3, COL_START)
    img.circb(start_x, start_y, 6, COL_START)
    img.save(str(filename), scale)
