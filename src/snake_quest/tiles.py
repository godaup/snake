"""Tile registry: sprite tiles (8px-tile coordinates in image bank 0) with a fixed meaning in every tilemap.

Tiles not listed here are either entity sprites (see `ENTITY_TILES` in entity.py, lifted out when a map loads) or
stray tiles, which a test rejects."""

from enum import Enum


class TileKind(Enum):
    """What a tile with a fixed meaning does (see TILE_KINDS)."""

    FLOOR = "floor"  # walkable, free for spawning
    WALL = "wall"  # deadly to touch
    PATH = "path"  # level design helper, lifted out of the tilemap and drawn as breadcrumbs
    EXIT = "exit"  # walkable, the target of `exit: true` goals
    PORTAL = "portal"  # walkable; entering one moves the head to the other portal of the same colour
    HAZARD = "hazard"  # walkable, but every hazard tile the head enters cuts HAZARD_CUT segments off the tail
    ICE = "ice"  # walkable, but slippery: the snake's heading drifts after its steering (ICE_GRIP)
    MIRROR = "mirror"  # walkable, but left and right are swapped while the head is on it
    WEB = "web"  # walkable, but a web holds the snake for a moment (WEB_HOLD), then it is torn
    MACHINE = "machine"  # walkable workshop terrain (plates, open gates, belts, levers; see workshop.py)


EMPTY_TILE = (0, 0)
# the wall tile level designers paint with; replaced by a hedge variant when the map loads
WALL_TILE = (0, 3)
# hedge variant for each combination of wall neighbours: tile (mask, 8) with mask bits N=1, E=2, S=4, W=8
WALL_VARIANT_ROW = 8
# the snake's trail in levels with `trail` (see Map._lay_trail): walls the map lays and lifts again while playing
TRAIL_TILE = (7, 10)
TRAIL_CRUMBLE_TILE = (8, 10)  # its last TRAIL_CRUMBLE seconds
TRAIL_CRUMBLE = 1.5
# the cave-in (arc 4, the `collapse` goal): cracked ceiling (dust falling) on floor the front is about to reach, then
# rubble, a wall for good
CRACK_TILE = (13, 10)
RUBBLE_TILE = (12, 10)
# airlock doors (arc 6, the `airlock` level option): shut, a wall; open, walkable (nothing spawns on it). The doors
# of a level take turns (see Map._cycle_doors)
DOOR_TILE = (14, 10)
DOOR_OPEN_TILE = (15, 10)
# the Workshop (arc 5, see workshop.py), in three colours each (red, blue, yellow): a plate is down while a crate
# rests on it or the snake lies on it; a gate is open while every plate of its colour is down; a lock opens for good
# when the head brings a key of its colour. Belts carry what lies on them (right, down, left, up); a lever reverses
# the belts of its room, the reset lever puts the room's crates back
PLATE_TILES = ((16, 10), (17, 10), (18, 10))
GATE_TILES = ((19, 10), (20, 10), (21, 10))
GATE_OPEN_TILES = ((22, 10), (23, 10), (24, 10))
LOCK_TILES = ((25, 10), (26, 10), (27, 10))
BELT_TILES = {(28, 10): (1, 0), (29, 10): (0, 1), (30, 10): (-1, 0), (31, 10): (0, -1)}
LEVER_TILES = ((0, 21), (1, 21))
RESET_TILE = (2, 21)
WALL_TILES = frozenset(
    {WALL_TILE, TRAIL_TILE, TRAIL_CRUMBLE_TILE, RUBBLE_TILE, DOOR_TILE, *GATE_TILES, *LOCK_TILES}
    | {(mask, WALL_VARIANT_ROW) for mask in range(16)}
)
# floor decorations (grass, flowers, stones): drawn, but walkable and free for spawning
# 6, 7: the caves' pebbles and shards; 8, 9: stars, a galaxy; 10, 11: the workshop's bench grid, an oil spot;
# 12, 13: the Keeper's clover and stepping stones
DECOR_TILES = frozenset((k, 9) for k in range(14))
FLOOR_TILES = frozenset({EMPTY_TILE} | DECOR_TILES)
# level design helper marking the intended route (e.g. through the maze); hidden until revealed
PATH_TILE = (3, 0)
# one portal tile per colour (cyan, pink, orange, lime); each colour used in a level must appear exactly twice
PORTAL_TILES = ((0, 10), (1, 10), (2, 10), (3, 10))
EXIT_TILE = (4, 10)
HAZARD_TILE = (5, 10)  # thorns
HAZARD_CUT = 5
ICE_TILE = (6, 10)
ICE_GRIP = 0.12  # share of the way to where the snake points that its heading turns per frame on ice
MIRROR_TILE = (9, 10)
# webs (arc 4): the head entering one is held (slowed to WEB_SLOW for WEB_HOLD seconds) and tears it; a torn web
# grows back after WEB_REGROW seconds. Spiders spin new ones (see caves.py)
WEB_TILE = (10, 10)
TORN_WEB_TILE = (11, 10)
WEB_SLOW = 0.35
WEB_HOLD = 1.2
WEB_REGROW = 8.0

TILE_KINDS: dict[tuple[int, int], TileKind] = {
    **{tile: TileKind.FLOOR for tile in FLOOR_TILES},
    **{tile: TileKind.WALL for tile in WALL_TILES},
    PATH_TILE: TileKind.PATH,
    **{tile: TileKind.PORTAL for tile in PORTAL_TILES},
    EXIT_TILE: TileKind.EXIT,
    HAZARD_TILE: TileKind.HAZARD,
    ICE_TILE: TileKind.ICE,
    MIRROR_TILE: TileKind.MIRROR,
    WEB_TILE: TileKind.WEB,
    TORN_WEB_TILE: TileKind.FLOOR,
    CRACK_TILE: TileKind.FLOOR,
    DOOR_OPEN_TILE: TileKind.FLOOR,
    **{tile: TileKind.MACHINE for tile in (*PLATE_TILES, *GATE_OPEN_TILES, *BELT_TILES, *LEVER_TILES, RESET_TILE)},
}
# tiles that stay in the tilemap after loading (walls only as hedge variants)
TERRAIN_TILES = frozenset(tile for tile, kind in TILE_KINDS.items() if kind != TileKind.PATH) - {WALL_TILE}


def tile_kind(tile: tuple[int, int]) -> TileKind | None:
    """Kind of a sprite tile, or None for entity sprites and anything else without a fixed meaning."""
    return TILE_KINDS.get(tile)
