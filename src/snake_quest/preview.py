"""Render a whole level to a PNG for reviewing level design (`snake-quest --level NAME --preview FILE`)."""

import datetime
from pathlib import Path

import omegaconf
import pyxel

from snake_quest.campaign import Level
from snake_quest.game import SETTINGS
from snake_quest.map import PATH_TILE, Map

COL_START = 7


class _PreviewGame:
    """Just enough of Game for Map to load a level."""

    def __init__(self):
        self.cfg = omegaconf.OmegaConf.load(SETTINGS)
        self.score = 0
        self.dt = datetime.timedelta(0)


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
        img.blt(pos.x, pos.y - header, 0, PATH_TILE[0] * 8, PATH_TILE[1] * 8, 8, 8, colkey=0)
    for ent in level_map.entities:
        img.blt(ent.pos.x, ent.pos.y - header, ent.img_b, ent.img_x, ent.img_y, ent.w, ent.h, colkey=0)
    start_x, start_y = level_map.start.x, level_map.start.y - header
    img.circ(start_x, start_y, 3, COL_START)
    img.circb(start_x, start_y, 6, COL_START)
    img.save(str(filename), scale)
