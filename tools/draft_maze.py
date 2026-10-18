"""Draft a maze around a designed pathway.

The level designer marks the intended route with path tiles on an 8-tile grid (see PATH_TILE in map.py). This script
builds a maze on that grid: cells of 7x7 floor tiles separated by 1-tile walls. The cells holding path tiles, the start
cell and the cell holding the golden apples are connected first; every other cell is then attached as a dead-end branch
(randomized Prim), so the result is a perfect maze whose only way to the golden apples runs along the pathway. Path
tiles and entity tiles are copied over unchanged, and the floor gets a sprinkle of decorations.

The draft is written to another tilemap of the same resource file, so the source layout stays untouched:

    python tools/draft_maze.py src/snake_quest/resources/garden.pyxres --level src/snake_quest/levels/maze.yaml \\
        --src-tm 2 --dst-tm 3 --seed 7

Review the result with `snake-quest --level maze --preview maze.png` after pointing the level's `tm` at the draft.
"""

import argparse
import random
from pathlib import Path

import omegaconf
import pyxel

from snake_quest.entity import ALL_ENTITIES, GoldenApple
from snake_quest.map import DECOR_TILES, EMPTY_TILE, PATH_TILE, WALL_TILE

PITCH = 8  # cell size in tiles, including one wall line
HEADER_H = 20  # world y of the map's top edge, see settings.yaml
GRASS, FLOWERS, STONE = sorted(DECOR_TILES)[:2], sorted(DECOR_TILES)[2:5], sorted(DECOR_TILES)[5]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("resources", type=Path)
    parser.add_argument("--level", type=Path, required=True, help="level YAML (for size and start position)")
    parser.add_argument("--src-tm", type=int, required=True)
    parser.add_argument("--dst-tm", type=int, required=True)
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def neighbours(cell, cols, rows):
    x, y = cell
    for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if 0 <= nxt[0] < cols and 0 <= nxt[1] < rows:
            yield nxt


def main() -> None:
    args = parse_args()
    resources = args.resources.resolve()  # before pyxel.init() changes the working directory
    level = omegaconf.OmegaConf.load(args.level)
    rng = random.Random(args.seed)
    pyxel.init(16, 16, headless=True)
    pyxel.load(str(resources))
    src, dst = pyxel.tilemaps[args.src_tm], pyxel.tilemaps[args.dst_tm]
    width, height = level.width // 8, level.height // 8
    cols, rows = width // PITCH, height // PITCH

    entity_sprites = {(cls._img_x, cls._img_y) for cls in ALL_ENTITIES}
    keep = {
        (x, y): src.pget(x, y)
        for y in range(height)
        for x in range(width)
        if src.pget(x, y) == PATH_TILE or src.pget(x, y) in entity_sprites
    }
    golden_sprite = (GoldenApple._img_x, GoldenApple._img_y)
    start_cell = (int(level.start.x) // 8 // PITCH, (int(level.start.y) - HEADER_H) // 8 // PITCH)
    golden_cells = {(x // PITCH, y // PITCH) for (x, y), tile in keep.items() if tile == golden_sprite}
    route = (
        {(x // PITCH, y // PITCH) for (x, y), tile in keep.items() if tile == PATH_TILE} | {start_cell} | golden_cells
    )

    # connect route components through other cells if the designed pathway has gaps
    components = 0
    unvisited = set(route)
    tree_edges: set[frozenset] = set()
    while unvisited:
        components += 1
        seed_cell = start_cell if start_cell in unvisited else min(unvisited)
        unvisited.discard(seed_cell)
        stack = [seed_cell]
        while stack:  # randomized DFS spanning tree over the route cells
            cell = stack[-1]
            options = [n for n in neighbours(cell, cols, rows) if n in unvisited]
            if not options:
                stack.pop()
                continue
            nxt = rng.choice(options)
            unvisited.discard(nxt)
            tree_edges.add(frozenset((cell, nxt)))
            stack.append(nxt)
    if components > 1:
        raise SystemExit(f"the pathway falls apart into {components} pieces; connect them in the source tilemap first")

    # attach every remaining cell as a dead-end branch (randomized Prim)
    in_maze = set(route)
    frontier = [(cell, n) for cell in in_maze for n in neighbours(cell, cols, rows) if n not in in_maze]
    while frontier:
        cell, nxt = frontier.pop(rng.randrange(len(frontier)))
        if nxt in in_maze:
            continue
        in_maze.add(nxt)
        tree_edges.add(frozenset((cell, nxt)))
        frontier += [(nxt, n) for n in neighbours(nxt, cols, rows) if n not in in_maze]

    # draw: walls everywhere, floor inside cells, openings for tree edges
    for y in range(height):
        for x in range(width):
            dst.pset(x, y, WALL_TILE)

    def interior(cx, cy):
        xs = range(cx * PITCH + 1, min(cx * PITCH + PITCH, width - 1))
        ys = range(cy * PITCH + 1, min(cy * PITCH + PITCH, height - 1))
        return xs, ys

    for cy in range(rows):
        for cx in range(cols):
            xs, ys = interior(cx, cy)
            for y in ys:
                for x in xs:
                    dst.pset(x, y, EMPTY_TILE)
    for edge in tree_edges:
        (ax, ay), (bx, by) = sorted(edge)
        xs, ys = interior(ax, ay)
        if ay == by:  # horizontal neighbours: open the wall column between them
            for y in ys:
                dst.pset(bx * PITCH, y, EMPTY_TILE)
        else:
            for x in xs:
                dst.pset(x, by * PITCH, EMPTY_TILE)

    misplaced = [pos for pos in keep if dst.pget(*pos) == WALL_TILE]
    if misplaced:
        raise SystemExit(f"path or entity tiles would end up inside walls: {misplaced}")
    for (x, y), tile in keep.items():
        dst.pset(x, y, tile)

    # decorate: mostly grass, some flowers, few stones, never next to the pathway
    near_path = {(x + dx, y + dy) for (x, y) in keep for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    decorated = 0
    for y in range(height):
        for x in range(width):
            if dst.pget(x, y) != EMPTY_TILE or (x, y) in near_path:
                continue
            roll = rng.random()
            if roll < 0.03:
                tile = rng.choice(GRASS)
            elif roll < 0.038:
                tile = rng.choice(FLOWERS)
            elif roll < 0.041:
                tile = STONE
            else:
                continue
            dst.pset(x, y, tile)
            decorated += 1

    dst.imgsrc = src.imgsrc
    pyxel.save(str(resources))
    print(
        f"maze {cols}x{rows} cells, route {len(route)} cells, golden cell(s) {sorted(golden_cells)}, "
        f"start {start_cell}, {len(keep)} path/entity tiles kept, {decorated} decorations -> tilemap {args.dst_tm}"
    )


if __name__ == "__main__":
    main()
