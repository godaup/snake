"""Tile registry: sprite tiles (8px-tile coordinates in image bank 0) with a fixed meaning in every tilemap.

Tiles not listed here are either entity sprites (see `ENTITY_TILES` in entity.py, lifted out when a map loads) or
stray tiles, which a test rejects."""

from enum import Enum


class TileKind(Enum):
    FLOOR = "floor"  # walkable, free for spawning
    WALL = "wall"  # deadly to touch
    PATH = "path"  # level design helper, lifted out of the tilemap and drawn as breadcrumbs
    EXIT = "exit"  # walkable, the target of `exit: true` goals
    PORTAL = "portal"  # walkable; entering one moves the head to the other portal of the same colour
    HAZARD = "hazard"  # walkable, but every hazard tile the head enters cuts HAZARD_CUT segments off the tail
    ICE = "ice"  # walkable, but slippery: the snake's heading drifts after its steering (ICE_GRIP)
    MIRROR = "mirror"  # walkable, but left and right are swapped while the head is on it


EMPTY_TILE = (0, 0)
# the wall tile level designers paint with; replaced by a hedge variant when the map loads
WALL_TILE = (0, 3)
# hedge variant for each combination of wall neighbours: tile (mask, 8) with mask bits N=1, E=2, S=4, W=8
WALL_VARIANT_ROW = 8
# the snake's trail in levels with `trail` (see Map._lay_trail): walls the map lays and lifts again while playing
TRAIL_TILE = (7, 10)
TRAIL_CRUMBLE_TILE = (8, 10)  # its last TRAIL_CRUMBLE seconds
TRAIL_CRUMBLE = 1.5
WALL_TILES = frozenset({WALL_TILE, TRAIL_TILE, TRAIL_CRUMBLE_TILE} | {(mask, WALL_VARIANT_ROW) for mask in range(16)})
# floor decorations (grass, flowers, stones): drawn, but walkable and free for spawning
DECOR_TILES = frozenset((k, 9) for k in range(6))
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

TILE_KINDS: dict[tuple[int, int], TileKind] = {
    **{tile: TileKind.FLOOR for tile in FLOOR_TILES},
    **{tile: TileKind.WALL for tile in WALL_TILES},
    PATH_TILE: TileKind.PATH,
    **{tile: TileKind.PORTAL for tile in PORTAL_TILES},
    EXIT_TILE: TileKind.EXIT,
    HAZARD_TILE: TileKind.HAZARD,
    ICE_TILE: TileKind.ICE,
    MIRROR_TILE: TileKind.MIRROR,
}
# tiles that stay in the tilemap after loading (walls only as hedge variants)
TERRAIN_TILES = frozenset(tile for tile, kind in TILE_KINDS.items() if kind != TileKind.PATH) - {WALL_TILE}


def tile_kind(tile: tuple[int, int]) -> TileKind | None:
    """Kind of a sprite tile, or None for entity sprites and anything else without a fixed meaning."""
    return TILE_KINDS.get(tile)
