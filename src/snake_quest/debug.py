"""Debug overlay for level design (`--debug`): what is under the mouse, in tile and world coordinates."""

from typing import TYPE_CHECKING

import pyxel

from snake_quest.tiles import tile_kind
from snake_quest.utils import Vec2

if TYPE_CHECKING:
    from snake_quest.states.running import RunningStateHandler

COL_CURSOR = 10
COL_LABEL, COL_LABEL_BG = 7, 0


def describe_tile(running: "RunningStateHandler", world: Vec2) -> str | None:
    """'TILE 12,5 WALL (3,8) POS 100,60' for a world position, with the entity there if any; None outside the map."""
    level_map = running.map
    tx, ty = level_map.tile_xy(world)
    if not (0 <= tx < level_map.cfg.width // 8 and 0 <= ty < level_map.cfg.height // 8):
        return None
    sprite = level_map.tile_at(world)
    kind = tile_kind(sprite)
    what = kind.name if kind else "?"
    for ent in level_map.entities:
        if ent.alive and ent.covers(world):
            what = getattr(ent, "name", type(ent).__name__).upper()
    header = running.game.cfg.header.h
    return f"TILE {tx},{ty} {what} ({sprite[0]},{sprite[1]}) POS {int(world.x)},{int(world.y) - header}"


def draw_overlay(running: "RunningStateHandler") -> None:
    """Crosshair at the mouse (the cursor is hidden while playing), the tile under it outlined, and a label."""
    cfg = running.game.cfg
    mx, my = pyxel.mouse_x, pyxel.mouse_y
    if not (0 <= mx < cfg.width and cfg.header.h <= my < cfg.header.h + cfg.area.h):
        return
    offset = running.cam.offset
    world = Vec2(mx - offset.x, my - offset.y)
    label = describe_tile(running, world)
    if label is None:
        return
    tx, ty = running.map.tile_xy(world)
    pyxel.rectb(tx * 8 + offset.x, ty * 8 + cfg.header.h + offset.y, 8, 8, COL_CURSOR)
    pyxel.line(mx - 3, my, mx + 3, my, COL_CURSOR)
    pyxel.line(mx, my - 3, mx, my + 3, COL_CURSOR)
    width = len(label) * pyxel.FONT_WIDTH + 3
    # label in the top corner of the play area away from the mouse, so it never hides what is being looked at
    x = 1 if mx > cfg.width / 2 else cfg.width - width - 1
    pyxel.rect(x, cfg.header.h + 1, width, pyxel.FONT_HEIGHT + 2, COL_LABEL_BG)
    pyxel.text(x + 2, cfg.header.h + 2, label, COL_LABEL)
