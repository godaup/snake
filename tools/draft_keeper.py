"""Write a Keeper level (the bonus arc) from its garden text: one character per tile (8 px).

    python tools/draft_keeper.py src/snake_quest/resources/keeper.pyxres tools/gardens/hedges.txt --tm 0

The text is the source of truth for the layout (edit it, then run this again); the tool prints the level's `width`,
`height` and `start` for its level file. Plain floor gets decorations scattered over it (grass, flowers, clover,
stepping stones; `--decor` share, the same every time for a text). Characters:

    #  wall (a hedge)     .  floor (a space too)     @  the start      *  thorns
    a  apple (fallen: none grows after it)           A  apple          G  golden apple
    N  nest               h  beetle (asleep)

Lines may be ragged: missing tiles are walls. A line starting with `;` is a comment.
"""

import argparse
import random
from pathlib import Path

import pyxel

from snake_quest.entity import ENTITY_NAMES
from snake_quest.tiles import EMPTY_TILE, HAZARD_TILE, WALL_TILE

TERRAIN = {"#": WALL_TILE, "*": HAZARD_TILE}
ENTITIES = {"a": "fallen", "A": "apple", "G": "golden", "N": "nest", "h": "hunter"}
DECOR = [(0, 9), (1, 9), (2, 9), (3, 9), (4, 9), (12, 9), (12, 9), (13, 9)]
HEADER = 20  # px above the play area (settings.yaml): world y of the map's top


def read(path: Path) -> list[str]:
    lines = [line.rstrip("\n") for line in path.read_text().splitlines() if not line.startswith(";")]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("resources", type=Path)
    parser.add_argument("garden", type=Path)
    parser.add_argument("--tm", type=int, required=True, help="tilemap to write")
    parser.add_argument("--decor", type=float, default=0.06, help="share of floor tiles decorated")
    args = parser.parse_args()
    resources = args.resources.resolve()  # pyxel.init changes the working directory
    lines = read(args.garden)
    width = max(len(line) for line in lines)
    rng = random.Random(args.garden.stem)
    pyxel.init(16, 16, headless=True)
    pyxel.load(str(resources))
    tilemap = pyxel.tilemaps[args.tm]
    for y in range(256):
        for x in range(256):
            tilemap.pset(x, y, EMPTY_TILE)
    start = None
    for y, line in enumerate(lines):
        for x in range(width):
            ch = line[x] if x < len(line) else "#"
            if ch in TERRAIN:
                tilemap.pset(x, y, TERRAIN[ch])
            elif ch in ENTITIES:
                cls = ENTITY_NAMES[ENTITIES[ch]]
                tilemap.pset(x, y, (cls._img_x, cls._img_y))
            elif ch in " .@":
                if ch == "@":
                    start = (x * 8 + 4, y * 8 + 4 + HEADER)
                if rng.random() < args.decor:
                    tilemap.pset(x, y, rng.choice(DECOR))
            else:
                raise SystemExit(f"{args.garden}:{y + 1}: unknown tile {ch!r}")
    pyxel.save(str(resources))
    print(f"width: {width * 8}\nheight: {len(lines) * 8}")
    if start:
        print(f"start:\n  x: {start[0]}\n  y: {start[1]}")


if __name__ == "__main__":
    main()
