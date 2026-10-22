"""Write a Workshop level (arc 5) from its puzzle text: one character per bench grid cell (16 px, two by two tiles).

    python tools/draft_workshop.py src/snake_quest/resources/arc5.pyxres --tm 0 tools/puzzles/crates.txt

The text is the source of truth for the layout (edit it, then run this again); the tool prints the level's `width`,
`height` and `start` for its level file. Characters:

    #  wall            .  floor (a space too)   @  the start         E  the exit
    $  crate           r b y  plate (red, blue, yellow)              R B Y  gate of that colour (shut)
    1 2 3  lock (red, blue, yellow)             4 5 6  key (red, blue, yellow)
    > v < ^  belt      ) V ( A  a crate on a belt (right, down, left, up)
    s  belt lever      x  reset lever           *  thorns
    a  apple           G  golden apple          m  clockwork mouse   o  mouse hole
    g  gun             h  homing

Entities go on the cell's top-left tile; terrain fills all four. Every floor cell gets the bench grid mark in its
corner. Lines may be ragged: missing cells are walls. A line starting with `;` is a comment.
"""

import argparse
from pathlib import Path

import pyxel

from snake_quest.entity import ENTITY_NAMES
from snake_quest.tiles import (
    BELT_TILES,
    EMPTY_TILE,
    EXIT_TILE,
    GATE_TILES,
    HAZARD_TILE,
    LEVER_TILES,
    LOCK_TILES,
    PLATE_TILES,
    RESET_TILE,
    WALL_TILE,
)

GRID_MARK = (10, 9)
BELTS = {direction: tile for tile, direction in BELT_TILES.items()}
TERRAIN = {
    "#": WALL_TILE,
    "E": EXIT_TILE,
    "*": HAZARD_TILE,
    "s": LEVER_TILES[0],
    "x": RESET_TILE,
    ">": BELTS[1, 0],
    "v": BELTS[0, 1],
    "<": BELTS[-1, 0],
    "^": BELTS[0, -1],
    **dict(zip("rby", PLATE_TILES, strict=True)),
    **dict(zip("RBY", GATE_TILES, strict=True)),
    **dict(zip("123", LOCK_TILES, strict=True)),
}
ON_BELT = {")": ">", "V": "v", "(": "<", "A": "^"}
ENTITIES = {
    "$": "crate",
    "4": "key_red",
    "5": "key_blue",
    "6": "key_yellow",
    "a": "apple",
    "G": "golden",
    "m": "mouse",
    "o": "mousehole",
    "g": "gun",
    "h": "homing",
}
HEADER = 20  # px above the play area (settings.yaml): world y of the map's top


def read(path: Path) -> list[str]:
    lines = [line.rstrip("\n") for line in path.read_text().splitlines() if not line.startswith(";")]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("resources", type=Path)
    parser.add_argument("puzzle", type=Path)
    parser.add_argument("--tm", type=int, required=True, help="tilemap to write")
    args = parser.parse_args()
    resources = args.resources.resolve()  # pyxel.init changes the working directory
    lines = read(args.puzzle)
    width = max(len(line) for line in lines)
    pyxel.init(16, 16, headless=True)
    pyxel.load(str(resources))
    tilemap = pyxel.tilemaps[args.tm]
    for y in range(256):
        for x in range(256):
            tilemap.pset(x, y, EMPTY_TILE)
    start = None
    for cy, line in enumerate(lines):
        for cx in range(width):
            ch = line[cx] if cx < len(line) else "#"
            tiles = [(cx * 2 + dx, cy * 2 + dy) for dy in (0, 1) for dx in (0, 1)]
            if ch in ON_BELT:  # a crate on a belt: the belt, the crate on its top left tile
                for tile in tiles:
                    tilemap.pset(*tile, TERRAIN[ON_BELT[ch]])
                crate = ENTITY_NAMES["crate"]
                tilemap.pset(*tiles[0], (crate._img_x, crate._img_y))
                continue
            if ch in TERRAIN:
                for tile in tiles:
                    tilemap.pset(*tile, TERRAIN[ch])
                continue
            tilemap.pset(*tiles[0], GRID_MARK)
            if ch == "@":
                start = (cx * 16 + 8, cy * 16 + 8 + HEADER)
            elif ch in ENTITIES:
                cls = ENTITY_NAMES[ENTITIES[ch]]
                tilemap.pset(*tiles[0], (cls._img_x, cls._img_y))
            elif ch not in " .":
                raise SystemExit(f"{args.puzzle}:{cy + 1}: unknown cell {ch!r}")
    pyxel.save(str(resources))
    print(f"width: {width * 16}\nheight: {len(lines) * 16}")
    if start:
        print(f"start:\n  x: {start[0]}\n  y: {start[1]}")


if __name__ == "__main__":
    main()
